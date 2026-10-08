const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let activeUrl;
export async function openPdf(url,title,show,notify,notice=''){
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok){const result=await response.json();throw new Error(result.error||'No se pudo generar el PDF.')}
  const blob=await response.blob();
  if(activeUrl)URL.revokeObjectURL(activeUrl);
  activeUrl=URL.createObjectURL(blob);
  const filename='mananera-'+title.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,'-').toLowerCase()+'.pdf';
  const file=new File([blob],filename,{type:'application/pdf'});
  const sharing=typeof navigator.canShare==='function'&&navigator.canShare({files:[file]});
  show(`<h2>${escape(title)}</h2>${notice?`<p class="help">${escape(notice)}</p>`:''}<p>PDF listo para guardar o compartir.</p><div class="actions"><a class="button-link" href="${activeUrl}" download="${filename}">Descargar PDF</a>${sharing?'<button type="button" id="share-pdf">Compartir PDF</button>':''}</div>${sharing?'<p class="help">Al compartir, puedes elegir WhatsApp si está instalado en tu celular.</p>':'<p class="help">Descarga el archivo y adjúntalo desde WhatsApp u otra aplicación.</p>'}`);
  const button=document.querySelector('#share-pdf');
  if(button)button.onclick=async()=>{
    try{await navigator.share({files:[file],title});}catch(error){if(error.name!=='AbortError')notify('No se pudo compartir. Puedes descargar el PDF y adjuntarlo manualmente.')}
  };
}

export async function savedPdf(recordId,title,hasLogo,show,notify){
  const notice=hasLogo?'Registro guardado. El PDF lleva el logo configurado.':'Registro guardado. Falta cargar el logo oficial en Administración; este PDF sale sin logo.';
  try{
    await openPdf('/api/pdf/'+encodeURIComponent(recordId),title,show,notify,notice);
    return true;
  }catch{
    show(`<h2>Registro guardado</h2><div class="success">Los datos ya están guardados. No necesitas volver a guardarlos.</div><p>No se pudo generar el PDF. Comprueba la conexión y vuelve a intentar.</p><button type="button" id="retry-saved-pdf">Generar PDF otra vez</button>`);
    const retry=document.querySelector('#retry-saved-pdf');
    if(retry)retry.onclick=async()=>{retry.disabled=true;await savedPdf(recordId,title,hasLogo,show,notify)};
    return false;
  }
}

export async function downloadBackup(notify){
  const response=await fetch('/api/backup',{cache:'no-store'});
  if(!response.ok){const result=await response.json();throw new Error(result.error||'No se pudo crear el respaldo.')}
  const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='respaldo-completo-mananera-'+new Date().toISOString().slice(0,10)+'.zip';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
  notify('Respaldo completo descargado: cuentas, usuarios y archivos. Guárdalo en un lugar seguro.');
}
