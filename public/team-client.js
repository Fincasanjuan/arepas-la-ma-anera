const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key=()=>crypto.randomUUID();
let user,root,notify=()=>{},show=()=>{},timer,polling=false,room='team',messages=[],cursor=0,info,sendKey=key(),pendingFile,draftText='',recorder,recordStream,recordTimer;
let activeCall,stream,signalCursor=0,heartbeat=0;
const peers=new Map(),pendingIce=new Map();

async function request(path,body){
  let response;
  try{response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});}catch{throw new Error('Sin conexión. Conservamos el mensaje para que puedas reintentarlo.')}
  const data=await response.json();if(!response.ok)throw new Error(data.error||'No se pudo completar la acción.');return data;
}
const action=(name,payload,requestKey=key())=>request('/api/action/team-'+name,{key:requestKey,payload:{room,...payload}});

export function setTeamUser(next,callbacks={}){
  if(callbacks.notify)notify=callbacks.notify;if(callbacks.show)show=callbacks.show;
  if(next?.id===user?.id){user=next;return}
  if(timer)clearInterval(timer);
  root=null;room='team';messages=[];cursor=0;info=null;
  stopLocalCall();stopRecorder(false);pendingFile=null;draftText='';
  user=next;
  if(user){poll();timer=setInterval(poll,2000)}
}

export function unmountTeam(){root=null;stopRecorder(false)}

export function mountTeam(container,currentUser,callbacks){
  notify=callbacks.notify;show=callbacks.show;setTeamUser(currentUser);root=container;
  root.innerHTML=`<div class="team-layout"><aside class="card team-sidebar"><h2>Conversaciones</h2><div id="team-rooms"></div><button type="button" id="team-new-room" class="secondary full-width">Nueva conversación</button></aside><section class="card team-conversation"><div class="team-title"><div><h2 id="team-room-name">Equipo La Mañanera</h2><p id="team-members" class="help"></p></div><div class="actions"><button type="button" data-team-call="audio" class="secondary small">Llamar</button><button type="button" data-team-call="video" class="secondary small">Videollamada</button></div></div><p id="team-connection" class="help" role="status">Conectando con el equipo…</p><button type="button" id="team-older" class="secondary small">Ver mensajes anteriores</button><div id="team-messages" class="team-messages" role="log" aria-label="Mensajes del equipo" aria-live="polite"></div><form id="team-composer"><label for="team-text">Mensaje</label><textarea id="team-text" rows="2" maxlength="4000" placeholder="Escribe al equipo…"></textarea><div id="team-file-preview" class="help"></div><div class="team-tools"><label class="file-button" for="team-file">Adjuntar archivo</label><input hidden id="team-file" type="file" accept="image/jpeg,image/png,image/webp,audio/mpeg,audio/wav,audio/ogg,audio/webm,audio/mp4,video/mp4,video/webm"><label class="file-button" for="team-camera">Cámara</label><input hidden id="team-camera" type="file" accept="image/jpeg,image/png" capture="environment"><button id="team-record" type="button" class="secondary small">Grabar audio</button></div><div id="team-stickers" class="team-stickers" aria-label="Stickers"></div><div class="team-send"><span id="team-send-status" role="status" class="help"></span><button type="submit">Enviar mensaje</button></div></form></section></div>`;
  root.querySelector('#team-composer').onsubmit=event=>{event.preventDefault();sendMessage()};
  root.querySelector('#team-text').value=draftText;
  root.querySelector('#team-text').oninput=event=>{draftText=event.target.value;sendKey=key()};
  for(const selector of ['#team-file','#team-camera'])root.querySelector(selector).onchange=event=>{const file=event.target.files[0];if(file)chooseFile(file)};
  root.querySelector('#team-new-room').onclick=newRoom;
  root.querySelector('#team-older').onclick=loadEarlier;
  root.querySelector('#team-record').onclick=toggleRecording;
  root.querySelectorAll('[data-team-call]').forEach(button=>button.onclick=()=>startCall(button.dataset.teamCall));
  renderMessages();if(info)renderInfo();poll();
}

async function poll(){
  if(!user||polling)return;
  const requestedRoom=room,requestedUser=user.id,requestedCall=activeCall?.id||null;
  polling=true;
  try{
    const query=new URLSearchParams({room,after:String(cursor)});
    if(activeCall){query.set('call',activeCall.id);query.set('callAfter',String(signalCursor))}
    const data=await request('/api/team?'+query);
    if(user?.id!==requestedUser)return;
    info=data;
    const ids=new Set(messages.map(m=>m.seq));
    if(room===requestedRoom)for(const message of data.messages){if(!ids.has(message.seq))messages.push(message);cursor=Math.max(cursor,message.seq)}
    if(root){root.querySelector('#team-connection').textContent='Conectado · Los mensajes se guardan en el servidor.';renderInfo();if(data.messages.length)renderMessages();}
    if((activeCall?.id||null)===requestedCall)await updateCall(data);
    if(activeCall&&Date.now()-heartbeat>20000){heartbeat=Date.now();await action('heartbeat',{id:activeCall.id,room:activeCall.room_id})}
  }catch(error){if(root)root.querySelector('#team-connection').textContent=error.message;const status=document.querySelector('#call-status');if(activeCall&&status)status.textContent='Sin conexión al servidor de llamadas. Puedes intentar de nuevo o colgar.';}
  finally{polling=false}
}

function renderInfo(){
  if(!root||!info)return;
  const current=info.rooms.find(r=>r.id===room);
  root.querySelector('#team-room-name').textContent=current?.title||'Conversación';
  root.querySelector('#team-members').textContent=current?.members.map(m=>m.name).join(' · ')||'';
  root.querySelector('#team-rooms').innerHTML=info.rooms.map(r=>`<button type="button" class="team-room ${r.id===room?'selected':''}" data-room="${r.id}">${escape(r.title)}</button>`).join('');
  root.querySelectorAll('[data-room]').forEach(button=>button.onclick=()=>changeRoom(button.dataset.room));
  if(!root.querySelector('#team-stickers').children.length){
    root.querySelector('#team-stickers').innerHTML=info.stickers.map(sticker=>`<button type="button" data-sticker="${sticker}" aria-label="Enviar sticker ${sticker}">${sticker}</button>`).join('');
    root.querySelectorAll('[data-sticker]').forEach(button=>button.onclick=()=>sendSticker(button.dataset.sticker));
  }
  root.querySelector('#team-older').hidden=messages.length<100;
}

function renderMessages(){
  if(!root)return;
  const log=root.querySelector('#team-messages');
  const nearBottom=log.scrollHeight-log.scrollTop-log.clientHeight<120;
  log.innerHTML=messages.length?messages.map(message=>{
    let file='';
    if(message.file){
      const src='/api/file/'+message.file.id,mime=message.file.mime;
      if(mime.startsWith('image/'))file=`<a href="${src}" target="_blank" rel="noopener"><img class="chat-photo" src="${src}" alt="${escape(message.file.name)}" loading="lazy"></a>`;
      else if(mime.startsWith('audio/'))file=`<audio controls preload="none" src="${src}" aria-label="Audio de ${escape(message.name)}"></audio>`;
      else file=`<video controls playsinline preload="metadata" src="${src}" aria-label="Video de ${escape(message.name)}"></video>`;
      file+=`<a class="help" href="${src}" download="${escape(message.file.name)}">Descargar ${escape(message.file.name)}</a>`;
    }
    return `<article class="chat-bubble ${message.sender===user.id?'mine':''}"><strong>${escape(message.name)}</strong>${message.content?`<p>${escape(message.content)}</p>`:''}${message.sticker?`<p class="sticker">${message.sticker}</p>`:''}${file}<div class="chat-meta">${escape(new Date(message.created).toLocaleString('es-CO',{timeZone:'America/Bogota',dateStyle:'short',timeStyle:'short'}))} · Enviado</div></article>`;
  }).join(''):'<div class="empty"><h3>Conversa con el equipo</h3><p>Los mensajes y archivos quedan separados de pedidos y cuentas.</p></div>';
  if(nearBottom||messages.length<=100)log.scrollTop=log.scrollHeight;
}

async function changeRoom(next){
  if(next===room)return;
  if(root&&(root.querySelector('#team-text').value||pendingFile)&&!confirm('Tienes un mensaje sin enviar. ¿Cambiar de conversación y descartarlo?'))return;
  room=next;messages=[];cursor=0;pendingFile=null;sendKey=key();draftText='';
  if(root){root.querySelector('#team-text').value='';root.querySelector('#team-file-preview').textContent='';renderMessages()}
  renderInfo();await poll();
}

async function loadEarlier(){
  if(!messages.length)return;
  try{
    const before=Math.min(...messages.map(m=>m.seq));
    const data=await request('/api/team?'+new URLSearchParams({room,before:String(before)}));
    const seen=new Set(messages.map(m=>m.seq));messages=[...data.messages.filter(m=>!seen.has(m.seq)),...messages];renderMessages();
    if(!data.messages.length)notify('No hay mensajes anteriores.');
  }catch(error){notify(error.message)}
}

function newRoom(){
  if(!info)return;
  show(`<h2>Nueva conversación</h2><p>Selecciona una persona para hablar en privado o varias para crear un grupo.</p><form id="team-room-form"><div class="field"><label for="room-title">Nombre del grupo (opcional)</label><input id="room-title" maxlength="100"></div><div class="team-people">${info.people.filter(p=>p.id!==user.id).map(p=>`<label><input type="checkbox" value="${p.id}">${escape(p.name)}</label>`).join('')}</div><p class="help">Las llamadas permiten hasta 8 participantes.</p><div id="team-room-error" role="status"></div><button type="submit">Abrir conversación</button></form>`);
  const form=document.querySelector('#team-room-form');
  let requestKey=key();form.oninput=()=>{requestKey=key()};
  form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;try{
    const selected=[...form.querySelectorAll('input[type=checkbox]:checked')].map(i=>i.value);
    const result=await action('room',{members:selected,title:form.querySelector('#room-title').value},requestKey);
    document.querySelector('#modal').close();await changeRoom(result.id);
  }catch(error){form.querySelector('#team-room-error').textContent=error.message}finally{button.disabled=false}};
}

async function chooseFile(file){
  if(file.size>12*1024*1024){notify('El archivo debe pesar máximo 12 MB.');return}
  const mime=file.type.split(';')[0];
  const allowed=['image/jpeg','image/png','image/webp','audio/mpeg','audio/wav','audio/ogg','audio/webm','audio/mp4','video/mp4','video/webm'];
  if(!allowed.includes(mime)){notify('Usa una imagen JPG, PNG o WebP, o un audio/video MP3, WAV, OGG, WebM o MP4.');return}
  try{
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('No se pudo leer el archivo.'));reader.readAsDataURL(file)});
    pendingFile={name:file.name,mime,data,key:key()};sendKey=key();
    if(root){const preview=root.querySelector('#team-file-preview');preview.innerHTML=`Adjunto: ${escape(file.name)} · ${Math.round(file.size/1024)} KB <button type="button" class="secondary small" id="remove-team-file">Quitar</button>`;preview.querySelector('button').onclick=()=>{pendingFile=null;preview.textContent='';sendKey=key()};}
  }catch(error){notify(error.message)}
}

async function sendMessage(){
  if(!root)return;
  const form=root.querySelector('#team-composer'),button=form.querySelector('button[type=submit]'),textarea=root.querySelector('#team-text'),status=root.querySelector('#team-send-status');
  if(button.disabled)return;
  const controls=[...form.querySelectorAll('button,input,textarea')];controls.forEach(el=>el.disabled=true);status.textContent='Pendiente de envío…';
  const targetRoom=room,file=pendingFile,currentText=textarea.value,attemptKey=sendKey;
  try{
    let fid=file?.id;
    if(file&&!fid){const uploaded=await action('file',{room:targetRoom,name:file.name,mime:file.mime,data:file.data},file.key);fid=uploaded.id;file.id=fid}
    await action('message',{room:targetRoom,text:currentText,file:fid},attemptKey);
    textarea.value='';
    if(sendKey===attemptKey&&room===targetRoom){draftText='';if(pendingFile===file)pendingFile=null;sendKey=key();if(root){root.querySelector('#team-text').value='';root.querySelector('#team-file-preview').textContent=''}}
    status.textContent='Enviado.';await poll();
  }catch(error){status.textContent=error.message}
  finally{controls.forEach(el=>el.disabled=false)}
}

async function sendSticker(sticker){try{await action('message',{sticker});await poll()}catch(error){notify(error.message)}}

async function toggleRecording(){
  if(recorder?.state==='recording'){stopRecorder(true);return}
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){notify('La grabación necesita un navegador compatible y una dirección HTTPS.');return}
  try{
    recordStream=await navigator.mediaDevices.getUserMedia({audio:true});
    const mime=['audio/webm','audio/mp4','audio/ogg'].find(type=>MediaRecorder.isTypeSupported(type));
    if(!mime)throw new Error('Este navegador no tiene un formato de audio compatible.');
    const chunks=[];recorder=new MediaRecorder(recordStream,{mimeType:mime});
    recorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data)};
    recorder.onstop=()=>{
      const keep=recorder?.keep;
      for(const track of recordStream?.getTracks()||[])track.stop();recordStream=null;recorder=null;
      if(root)root.querySelector('#team-record').textContent='Grabar audio';
      if(keep&&chunks.length){const extension=mime==='audio/mp4'?'m4a':mime==='audio/ogg'?'ogg':'webm';chooseFile(new File(chunks,'audio-'+Date.now()+'.'+extension,{type:mime}))}
    };
    recorder.start();root.querySelector('#team-record').textContent='Finalizar audio';
    root.querySelector('#team-send-status').textContent='Grabando audio. Al finalizar, toca Enviar mensaje.';
    recordTimer=setTimeout(()=>stopRecorder(true),60000);
  }catch(error){for(const track of recordStream?.getTracks()||[])track.stop();recordStream=null;notify(error.name==='NotAllowedError'?'Permite el micrófono para grabar audio.':error.message)}
}

function stopRecorder(keep){
  clearTimeout(recordTimer);
  if(recorder&&recorder.state!=='inactive'){recorder.keep=keep;recorder.stop()}
  else{for(const track of recordStream?.getTracks()||[])track.stop();recordStream=null}
}

async function obtainMedia(kind){
  if(!navigator.mediaDevices?.getUserMedia||typeof RTCPeerConnection==='undefined')throw new Error('La llamada necesita HTTPS y un navegador compatible con cámara y micrófono.');
  return navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:kind==='video'});
}

async function startCall(kind){
  if(activeCall){notify('Ya estás en una llamada.');return}
  let acquired;
  try{
    acquired=await obtainMedia(kind);
    const result=await action('call',{kind});
    stream=acquired;activeCall={id:result.id,room_id:room,kind};signalCursor=0;heartbeat=0;renderActiveCall();await poll();
  }catch(error){for(const track of acquired?.getTracks()||[])track.stop();notify(error.name==='NotAllowedError'?'Permite el micrófono y la cámara para llamar.':error.message)}
}

async function acceptCall(call){
  if(activeCall)return;
  let acquired;
  try{
    acquired=await obtainMedia(call.kind);
    await action('join',{room:call.room_id,id:call.id});
    stream=acquired;activeCall=call;signalCursor=0;heartbeat=0;renderActiveCall();await poll();
  }catch(error){for(const track of acquired?.getTracks()||[])track.stop();notify(error.name==='NotAllowedError'?'Permite el micrófono y la cámara para contestar.':error.message)}
}

function renderActiveCall(){
  const panel=document.querySelector('#call-panel');if(!panel)return;
  panel.hidden=false;panel.className='call-panel';
  panel.innerHTML=`<div class="call-top"><div><strong>${activeCall.kind==='video'?'Videollamada':'Llamada del equipo'}</strong><p id="call-status" role="status">Conectando con las personas…</p></div><button type="button" id="call-hangup" class="danger">Colgar</button></div><div class="call-media"><div class="call-local"><video muted autoplay playsinline id="call-local-video"></video><span>Tú</span></div><div id="call-peers"></div></div><div class="actions"><button id="call-mute" type="button" class="secondary small">Silenciar micrófono</button>${activeCall.kind==='video'?'<button id="call-camera" type="button" class="secondary small">Apagar cámara</button>':''}</div><p class="help">Si la conexión no se establece, puede faltar el servicio de conexión de llamadas del servidor.</p>`;
  panel.querySelector('#call-local-video').srcObject=stream;
  if(activeCall.kind==='audio')panel.querySelector('.call-local').hidden=true;
  panel.querySelector('#call-hangup').onclick=hangup;
  panel.querySelector('#call-mute').onclick=event=>{const tracks=stream.getAudioTracks(),enabled=!tracks[0]?.enabled;for(const track of tracks)track.enabled=enabled;event.target.textContent=enabled?'Silenciar micrófono':'Activar micrófono'};
  if(activeCall.kind==='video')panel.querySelector('#call-camera').onclick=event=>{const tracks=stream.getVideoTracks(),enabled=!tracks[0]?.enabled;for(const track of tracks)track.enabled=enabled;event.target.textContent=enabled?'Apagar cámara':'Encender cámara'};
}

async function hangup(){
  const call=activeCall;stopLocalCall();
  if(call)try{await action('leave',{room:call.room_id,id:call.id})}catch{notify('Se cerraron el micrófono y la cámara. El servidor cerrará la sesión de llamada al vencer la conexión.')}
}

function stopLocalCall(){
  for(const pc of peers.values())pc.close();peers.clear();pendingIce.clear();
  for(const track of stream?.getTracks()||[])track.stop();stream=null;activeCall=null;signalCursor=0;
  const panel=document.querySelector('#call-panel');if(panel){panel.hidden=true;panel.innerHTML='';panel.dataset.invitation=''}
}

async function updateCall(data){
  const panel=document.querySelector('#call-panel');
  if(activeCall){
    const call=data.calls.find(c=>c.id===activeCall.id),me=call?.members.find(m=>m.user_id===user.id);
    if(!call||me?.status!=='joined'){stopLocalCall();notify('La llamada terminó.');return}
    activeCall=call;
    const joined=call.members.filter(m=>m.status==='joined'&&m.user_id!==user.id);
    for(const [uid,pc] of peers)if(!joined.some(m=>m.user_id===uid)){pc.close();peers.delete(uid);document.querySelector('#peer-'+uid)?.remove()}
    for(const member of joined){
      if(!peers.has(member.user_id)){
        const pc=makePeer(member.user_id,member.name,data.iceServers);
        if(user.id<member.user_id){await pc.setLocalDescription(await pc.createOffer());await signal(member.user_id,'offer',pc.localDescription.toJSON())}
      }
    }
    for(const s of data.signals){
      try{await processSignal(s,data)}catch(error){notify('No se pudo conectar una de las personas. Puedes colgar y volver a llamar.')}
      signalCursor=Math.max(signalCursor,s.seq);
    }
    updateCallStatus();
  }else if(panel){
    const incoming=data.calls.find(call=>call.members.some(m=>m.user_id===user.id&&m.status==='invited'));
    if(incoming){
      if(panel.dataset.invitation!==incoming.id){
        panel.hidden=false;panel.dataset.invitation=incoming.id;panel.className='call-panel incoming';
        panel.innerHTML=`<strong>${escape(incoming.callerName)} te está llamando</strong><p>${incoming.kind==='video'?'Videollamada':'Llamada de audio'} · ${incoming.members.map(m=>escape(m.name)).join(', ')}</p><div class="actions"><button type="button" id="call-accept">Aceptar</button><button type="button" id="call-reject" class="secondary">Rechazar</button></div>`;
        panel.querySelector('#call-accept').onclick=()=>acceptCall(incoming);
        panel.querySelector('#call-reject').onclick=async()=>{try{await action('reject',{room:incoming.room_id,id:incoming.id});panel.hidden=true;panel.dataset.invitation='';await poll()}catch(error){notify(error.message)}};
      }
    }else{panel.hidden=true;panel.innerHTML='';panel.dataset.invitation=''}
  }
}

function makePeer(uid,name,iceServers){
  const pc=new RTCPeerConnection({iceServers});peers.set(uid,pc);
  for(const track of stream.getTracks())pc.addTrack(track,stream);
  pc.onicecandidate=event=>{if(event.candidate)signal(uid,'ice',event.candidate.toJSON()).catch(()=>notify('Hay dificultades para conectar la llamada.'))};
  pc.onconnectionstatechange=updateCallStatus;
  pc.ontrack=event=>{
    const grid=document.querySelector('#call-peers');if(!grid)return;
    let box=document.querySelector('#peer-'+uid);
    if(!box){box=document.createElement('div');box.className='call-remote';box.id='peer-'+uid;box.innerHTML=`<video autoplay playsinline controls></video><span>${escape(name)}</span>`;grid.append(box)}
    const media=box.querySelector('video');media.srcObject=event.streams[0]||new MediaStream([event.track]);media.play().catch(()=>notify('Toca reproducir para escuchar a '+name+'.'));
    if(activeCall.kind==='audio')box.classList.add('audio-only');
  };
  return pc;
}

async function signal(to,kind,value){
  const call=activeCall;if(!call)return;
  const requestKey=key(),payload={room:call.room_id,id:call.id,to,kind,signal:value};
  try{return await action('signal',payload,requestKey)}catch{return await action('signal',payload,requestKey)}
}

async function processSignal(s,data){
  let pc=peers.get(s.sender);
  if(!pc){const member=activeCall.members.find(m=>m.user_id===s.sender);if(!member||member.status!=='joined')return;pc=makePeer(s.sender,member.name,data.iceServers)}
  if(s.kind==='ice'){
    if(pc.remoteDescription)await pc.addIceCandidate(s.payload);
    else{const queue=pendingIce.get(s.sender)||[];queue.push(s.payload);pendingIce.set(s.sender,queue)}
  }else{
    await pc.setRemoteDescription(s.payload);
    for(const candidate of pendingIce.get(s.sender)||[])await pc.addIceCandidate(candidate);pendingIce.delete(s.sender);
    if(s.kind==='offer'){await pc.setLocalDescription(await pc.createAnswer());await signal(s.sender,'answer',pc.localDescription.toJSON())}
  }
}

function updateCallStatus(){
  const el=document.querySelector('#call-status');if(!el||!activeCall)return;
  const connected=[...peers.values()].filter(pc=>pc.connectionState==='connected').length;
  const failed=[...peers.values()].some(pc=>['failed','disconnected'].includes(pc.connectionState));
  if(connected)el.textContent='Conectada con '+connected+' persona'+(connected===1?'':'s')+'.'+(failed?' Hay una persona con dificultades de conexión.':'');
  else if(failed)el.textContent='La conexión de audio/video falló. Revisa la red o la configuración de llamadas.';
  else el.textContent=peers.size?'Conectando audio y video…':'Esperando a que el equipo conteste…';
}

document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll()});
