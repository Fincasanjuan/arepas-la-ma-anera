"""Complete, checked backups: SQLite snapshot plus original communication files."""
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def create_archive(db, data_dir, created):
    with tempfile.TemporaryDirectory() as temp:
        snapshot=Path(temp)/'database.sqlite3'
        target=sqlite3.connect(snapshot)
        try:
            db.backup(target)
            # Restoring a backup must never restore valid logged-in sessions.
            target.execute('DELETE FROM sessions')
            target.execute('DELETE FROM login_attempts')
            target.commit()
            files=list(target.execute('SELECT path FROM chat_files'))
        finally:
            target.close()
        contents={'database.sqlite3':snapshot.read_bytes()}
        for (name,) in files:
            if Path(name).name!=name:
                raise ValueError('Nombre de archivo inválido en el respaldo.')
            path=Path(data_dir)/'attachments'/name
            if not path.is_file():
                raise ValueError('Falta un archivo adjunto. No se puede crear un respaldo completo.')
            contents['attachments/'+name]=path.read_bytes()
        manifest={'format':'arepas-complete-backup','version':1,'created':created,
                  'sha256':{name:hashlib.sha256(value).hexdigest() for name,value in contents.items()}}
        result=io.BytesIO()
        with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,value in contents.items():
                archive.writestr(name,value)
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        return result.getvalue()


def restore_archive(archive_path, data_dir):
    """Restore only to an empty destination. Stop the app before restoring."""
    destination=Path(data_dir)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('El destino debe estar vacío. No se reemplazan datos existentes.')
    with zipfile.ZipFile(archive_path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or len(names)>100000:
            raise ValueError('Respaldo inválido.')
        if sum(info.file_size for info in archive.infolist())>2*1024**3:
            raise ValueError('Respaldo demasiado grande para esta herramienta.')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!='arepas-complete-backup' or manifest.get('version')!=1:
            raise ValueError('Formato de respaldo inválido.')
        expected=manifest.get('sha256',{})
        if set(names)!=(set(expected)|{'manifest.json'}) or 'database.sqlite3' not in expected:
            raise ValueError('El respaldo no está completo.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
            staging=Path(temp)
            for name,digest in expected.items():
                parts=Path(name).parts
                if name!='database.sqlite3' and not (len(parts)==2 and parts[0]=='attachments' and parts[1] not in ('.','..')):
                    raise ValueError('Ruta inválida dentro del respaldo.')
                content=archive.read(name)
                if hashlib.sha256(content).hexdigest()!=digest:
                    raise ValueError('El respaldo está dañado: '+name)
                path=staging/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(content)
            db=sqlite3.connect(staging/'database.sqlite3')
            try:
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('La base de datos del respaldo está dañada.')
                file_paths=[r[0] for r in db.execute('SELECT path FROM chat_files')]
                if any('attachments/'+name not in expected for name in file_paths):
                    raise ValueError('Faltan adjuntos del chat.')
                db.execute('DELETE FROM sessions')
                db.execute('DELETE FROM login_attempts')
                db.commit()
            finally:
                db.close()
            destination.mkdir(parents=True,exist_ok=True)
            (destination/'attachments').mkdir(exist_ok=True)
            # Names were validated before any file is moved to the final destination.
            for name in expected:
                target=destination/('arepas.sqlite3' if name=='database.sqlite3' else name)
                os.replace(staging/name,target)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Recuperar un respaldo completo de Arepas La Mañanera.')
    parser.add_argument('archivo',type=Path)
    parser.add_argument('--destino',type=Path,required=True,help='Directorio vacío para la base y los archivos.')
    args=parser.parse_args()
    restore_archive(args.archivo,args.destino)
    print('Respaldo recuperado. Inicia el servidor usando AREPAS_DATA_DIR con este directorio.')
