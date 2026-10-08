import {labels,statuses,pesos,decimal,productionPlan,routePreview} from './domain.js';
import {mountTeam,unmountTeam,setTeamUser} from './team-client.js';
import {openPdf,downloadBackup,savedPdf} from './pdf-client.js';
let S,tab='pedidos',filterDate='',filterRider='',installPrompt;
const app=document.querySelector('#app'),modal=document.querySelector('#modal');
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const id=()=>crypto.randomUUID();
const byId=value=>S.records?.find(r=>r.id===value);
const live=kind=>(S.records||[]).filter(r=>r.kind===kind&&r.status!=='void');
const who=owner=>S.users?.find(u=>u.id===owner)?.name||S.user?.name||'Repartidor';
const isAdmin=()=>S.user?.role==='admin';
const qtyInputs=(prefix='qty',values=[])=>`<div class="qty-list">${S.products.map((name,i)=>`<div class="qty-row"><label for="${prefix}-${i}">${esc(name)}</label><input id="${prefix}-${i}" name="${prefix}${i}" type="number" min="0" step="1" value="${values[i]||0}" inputmode="numeric" required></div>`).join('')}</div>`;
const field=(name,label,type='text',value='',extra='')=>`<div class="field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}></div>`;
const riderSelect=(name='rider')=>`<div class="field"><label for="${name}">Repartidor</label><select id="${name}" name="${name}" required><option value="">Selecciona una persona</option>${(S.users||[]).filter(u=>u.role==='rider').map(u=>`<option value="${u.id}">${esc(u.name)}</option>`).join('')}</select></div>`;
const messageArea='<div class="form-message" role="status"></div>';
const button=(label)=>`${messageArea}<button type="submit" class="full-width">${label}</button>`;
const empty=(title,help)=>`<div class="empty"><h3>${title}</h3><p>${help}</p></div>`;
function notify(message){const el=document.querySelector('#toast');el.textContent=message;el.classList.add('show');clearTimeout(notify.timer);notify.timer=setTimeout(()=>el.classList.remove('show'),5000)}
async function api(path,body){
  let response;
  try{response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});}catch{throw new Error('Sin conexión al servidor. El formulario sigue aquí; intenta de nuevo cuando vuelva la conexión.')}
  const result=await response.json();if(!response.ok)throw new Error(result.error||'No se pudo completar la acción.');return result;
}
async function refresh(){S=await api('/api/state');if(S.user&&!tabs().some(([key])=>key===tab))tab='pedidos';render()}
function tabs(){
  if(!S.user)return [['pedidos','Hacer pedido'],['acceso','Ingresar']];
  if(S.user.role==='rider')return [['pedidos','Mis pedidos'],['despachos','Despachos'],['rutas','Cierre de ruta'],['cuentas','Mis cuentas'],['equipo','Chat del equipo']];
  if(S.user.role==='dispatcher')return [['pedidos','Pedidos'],['despachos','Despachos'],['inventario','Inventario'],['equipo','Chat del equipo']];
  return [['pedidos','Pedidos'],['produccion','Producción'],['inventario','Inventario'],['despachos','Despachos'],['rutas','Cierres de ruta'],['cuentas','Fiados y abonos'],['equipo','Chat del equipo'],['informes','Informes'],['asistente','Asistente Gemini'],['admin','Administración']];
}
function render(){
  unmountTeam();
  setTeamUser(S.user,{notify,show:openModal});
  const brand=S.logo?`<img src="${esc(S.logo)}" alt="Logo oficial de Arepas La Mañanera">`:'';
  app.innerHTML=`<header><div class="brand">${brand}<div class="wordmark"><strong>Arepas La Mañanera</strong><span>${S.user?esc({admin:'Administración',rider:'Repartidor',dispatcher:'Despachador'}[S.user.role]):'Pedidos de la fábrica'}</span></div></div><div class="header-actions">${S.user?`<span>${esc(S.user.name)}</span><button class="secondary small" data-action="logout">Salir</button>`:''}</div></header><div class="shell"><nav aria-label="Secciones"><div class="navlabel">La fábrica</div>${tabs().map(([key,label])=>`<button data-tab="${key}" class="${tab===key?'active':''}" ${tab===key?'aria-current="page"':''}>${label}</button>`).join('')}</nav><main>${content()}<footer>Hora de Colombia · ${esc(S.today)}<details><summary>Instalar en el celular</summary><div class="install-info"><p>Con la aplicación publicada en una dirección segura, ábrela en Chrome y elige «Instalar aplicación» o «Añadir a pantalla de inicio». En iPhone: Safari, Compartir, «Añadir a pantalla de inicio».</p><p>Necesitas conexión para guardar y consultar los datos de la fábrica.</p>${installPrompt?'<button class="small" data-action="install">Instalar aplicación</button>':''}</div></details></footer></main></div>`;
  bindForms();
  if(tab==='equipo'&&S.user)mountTeam(document.querySelector('#team-root'),S.user,{notify,show:openModal});
}
function heading(title,sub=''){return `<div class="topline"><div><p class="eyebrow">${tab==='acceso'?'Tu acceso':'La fábrica, al día'}</p><h1>${title}</h1>${sub?`<p class="muted">${sub}</p>`:''}</div><span class="badge">${esc(S.today)}</span></div>`}
function filters(){return `<div class="filters"><div class="field"><label for="filter-date">Fecha</label><input id="filter-date" type="date" value="${filterDate}" data-filter="date"></div>${isAdmin()?`<div class="field"><label for="filter-rider">Repartidor</label><select id="filter-rider" data-filter="rider"><option value="">Todos</option>${(S.users||[]).filter(u=>u.role==='rider').map(u=>`<option value="${u.id}" ${filterRider===u.id?'selected':''}>${esc(u.name)}</option>`).join('')}</select></div>`:''}<button class="secondary small" data-action="clearFilters">Ver todo</button></div>`}
function filtered(records){return records.filter(r=>(!filterDate||r.date===filterDate)&&(!filterRider||r.owner===filterRider))}
function recordList(records){
  if(!records.length)return empty('Todavía no hay registros','Los movimientos guardados aparecerán aquí.');
  return records.map(r=>{
    const p=r.payload,amount=['debt','close'].includes(r.kind)?r.balance:p.total??p.amount??p.balance;
    const summary=p.qty?S.products.map((n,i)=>p.qty[i]?`${esc(n)}: ${p.qty[i]}`:'').filter(Boolean).join(' · '):p.reason?esc(p.reason):p.debtor?esc(p.debtor):'';
    const actions=[`<button class="secondary small" data-action="detail" data-id="${r.id}">Ver detalle</button>`];
    if(r.kind==='dispatch'&&r.status==='draft')actions.push(`<button class="small" data-action="confirm" data-id="${r.id}">Confirmar despacho</button>`);
    if(r.kind==='dispatch'&&r.status==='confirmed'&&S.user.role!=='dispatcher')actions.push(`<button class="small" data-action="route" data-id="${r.id}">Cerrar ruta</button>`);
    if(r.kind==='debt'&&r.status!=='void'&&r.balance>0&&isAdmin())actions.push(`<button class="small" data-action="payment" data-id="${r.id}">Registrar abono</button>`);
    if(r.kind==='close'&&r.status==='pending'&&isAdmin())actions.push(`<button class="small" data-action="settle" data-id="${r.id}">Revisar cierre</button>`);
    if(r.kind==='close'&&r.status!=='void'&&r.balance>0&&isAdmin())actions.push(`<button class="small" data-action="routePayment" data-id="${r.id}">Recibir saldo de ruta</button>`);
    if(r.status!=='draft')actions.push(`<button class="secondary small" data-action="print" data-id="${r.id}">Descargar / compartir PDF</button>`);
    if(isAdmin()&&r.status!=='void')actions.push(`<button class="danger small" data-action="void" data-id="${r.id}">Anular</button>`);
    return `<article class="record"><div class="record-head"><div><strong>${esc(p.name||p.debtor||who(r.owner))}</strong><div class="record-meta">${labels[r.kind]} · ${r.date}${amount!==undefined?' · '+pesos(amount):''}</div></div><span class="status ${r.status}">${statuses[r.status]}</span></div>${summary?`<p class="mini">${summary}</p>`:''}<div class="actions">${actions.join('')}</div></article>`;
  }).join('');
}
function orderForm(){return `<div class="card"><h2>Nuevo pedido</h2><form data-form="order"><div class="row">${field('name','Nombre del repartidor','text',S.user?.role==='rider'?S.user.name:'','required maxlength="100" autocomplete="name"')}${field('phone','Celular','tel',S.user?.role==='rider'?S.user.phone:'','required inputmode="tel" pattern="[0-9]{7,15}" autocomplete="tel"')}</div>${field('date','Fecha de entrega','date',S.orderDay,`required min="${S.orderDay}"`)}<p class="help">Después de las 12 del mediodía, el pedido más cercano es para mañana. No necesitas código para pedir.</p>${qtyInputs()}<div class="total"><span>Total de unidades de despacho</span><strong data-qty-total>0</strong></div>${button('Guardar pedido')}</form></div>`}
function content(){
  if(tab==='asistente'&&isAdmin())return heading('Asistente Gemini','Genera un resumen, revísalo y guárdalo como PDF.')+`<div class="card"><h2>Resumen de la fábrica</h2>${S.aiEnabled?'':'<p class="error">Gemini todavía no está conectado. Esta función estará disponible cuando se configure la conexión.</p>'}<form data-form="ai-generate">${field('question','¿Qué quieres consultar?','text','Resume las ventas, los gastos y los saldos pendientes.','required maxlength="1000"')}<p class="help">Se envían a Google tu consulta y totales de la fábrica. No se envían automáticamente nombres de clientes, celulares, chats ni archivos. El uso está sujeto a los límites y condiciones de tu cuenta Gemini.</p><label class="check-line"><input type="checkbox" name="consent" required> Quiero enviar estos resúmenes a Gemini.</label>${button('Generar resumen')}</form><p class="help">Las recomendaciones se revisan antes de guardarlas. No cambian cuentas ni inventario.</p></div><div class="card"><h2>Informes guardados</h2>${recordList(live('aiReport'))}</div>`;
  if(S.needsSetup)return heading('Comencemos desde cero')+`<div class="setup card yellow"><h2>Crear Administración</h2><p>Configura tu cuenta en el equipo donde se ejecuta la aplicación. La base de datos está vacía.</p><form data-form="setup">${field('name','Nombre','text','Dujardy','required')}${field('code','Contraseña de Administración','password','','required minlength="12" autocomplete="new-password"')}<p class="help">Usa al menos 12 caracteres. Para ingresar después, escribe «admin» en el campo de celular.</p>${button('Crear mi cuenta')}</form></div>`;
  if(tab==='acceso')return heading('Ingresa a tu espacio')+`<div class="setup card"><form data-form="login">${field('phone','Celular o «admin»','text','','required autocomplete="username"')}${field('code','Código personal','password','','required autocomplete="current-password"')}${button('Ingresar')}</form></div>`;
  if(tab==='pedidos'){
    const records=filtered((S.records||[]).filter(r=>r.kind==='order'));
    return heading(S.user?'Pedidos':'Haz tu pedido','Las cantidades se guardan por referencia y fecha de entrega.')+`<div class="grid">${S.user?.role==='dispatcher'?'':orderForm()}${S.user?`<div class="card"><h2>${S.user.role==='rider'?'Mis pedidos guardados':'Pedidos recibidos'}</h2>${filters()}${recordList(records)}</div>`:`<div class="card yellow"><h2>Tu pedido queda en la fábrica</h2><p>Escribe tu nombre, celular y las cantidades que necesitas.</p><p>Para consultar tus pedidos y despacharte, ingresa con el código personal que te entrega Administración.</p><button data-tab="acceso" class="secondary">Ingresar con mi código</button></div>`}</div>`;
  }
  if(tab==='despachos'){
    const own=S.user.role==='rider'?S.user.id:'';
    const draft=live('dispatch').find(r=>r.status==='draft'&&(own?r.owner===own:true));
    return heading('Prepara tu despacho','Guarda el borrador. Confírmalo cuando las cantidades estén revisadas.')+`<div class="grid"><div class="card"><h2>Borrador de despacho</h2><form data-form="draft">${own?'':riderSelect()}${qtyInputs('qty',own?draft?.payload.qty:[])}<p class="help">Guardar el borrador no descuenta inventario. El despacho confirmado conserva sus precios y cantidades.</p>${button('Guardar borrador')}</form></div><div class="card"><h2>Despachos guardados</h2>${filters()}${recordList(filtered((S.records||[]).filter(r=>r.kind==='dispatch')))}</div></div>`;
  }
  if(tab==='rutas')return heading('Cierres de ruta','Registra el regreso desde un despacho confirmado.')+`<div class="card"><h2>Rutas por cerrar</h2>${recordList(filtered(live('dispatch').filter(r=>r.status==='confirmed')))}</div><div class="card"><h2>Cierres enviados</h2>${filters()}${recordList(filtered((S.records||[]).filter(r=>r.kind==='close')))}</div><div class="card"><h2>Entregas de saldos</h2>${recordList(filtered(live('routePayment')))}</div>`;
  if(tab==='inventario')return heading('Inventario','Existencias disponibles según los movimientos registrados.')+`<div class="card"><h2>Producto terminado</h2>${stockTable(S.products)}</div><div class="grid"><div class="card"><h2>Insumos</h2>${stockTable(S.inputs)}</div>${isAdmin()?`<div class="card"><h2>Registrar entrada</h2><form data-form="input"><div class="field"><label for="item">Insumo</label><select name="item" id="item">${S.inputs.map(n=>`<option>${esc(n)}</option>`).join('')}</select></div><p class="help">Maíz: bultos · Químico: gramos · Bolsas: unidades. Mantén siempre la misma unidad para harina y sal.</p><div class="row">${field('qty','Cantidad','number','','required min="0.001" step="0.001"')}${field('unit','Unidad','text','bultos','required')}</div>${field('cost','Costo total ($)','number','','required min="0" step="1"')}${button('Guardar entrada')}</form></div>`:''}</div>`;
  if(tab==='produccion'){
    const day=filterDate||S.orderDay;
    const plan=productionPlan(live('order').filter(r=>r.date===day),S.products,S.config,S.stock);
    return heading('Producción','Calcula lo que hace falta y registra lo producido.')+`<div class="card yellow"><h2>Requerimiento para ${day}</h2>${filters()}<div class="tablewrap"><table><thead><tr><th>Referencia</th><th class="right">Pedidas</th><th class="right">Por producir</th></tr></thead><tbody>${S.products.map((n,i)=>`<tr><td>${esc(n)}</td><td class="right">${plan.totals[i]}</td><td class="right">${plan.missing[i]}</td></tr>`).join('')}</tbody></table></div><p>${plan.bultos===null?'Configura los rendimientos en Administración para calcular maíz y químico.':`Maíz estimado: <strong>${decimal(plan.bultos)} bultos</strong> · Químico: <strong>${decimal(plan.chemicalGrams)} g</strong> (${decimal(plan.bultos)} × 400 g).`}</p></div><div class="grid"><div class="card"><h2>Registrar producción</h2><form data-form="production"><div class="field"><label for="corn">Maíz utilizado</label><select id="corn" name="corn"><option>Maíz blanco</option><option>Maíz amarillo</option></select></div>${qtyInputs()}<div class="row">${field('flour','Harina utilizada','number',0,'min="0" step="0.001" required')}${field('salt','Sal utilizada','number',0,'min="0" step="0.001" required')}</div><p class="help">El maíz, el químico y las bolsas se descuentan según los rendimientos configurados. Primero registra las entradas de insumos.</p>${button('Guardar producción')}</form></div><div class="card"><h2>Producción guardada</h2>${recordList(filtered((S.records||[]).filter(r=>r.kind==='production')))}</div></div>`;
  }
  if(tab==='cuentas'){
    const debts=filtered(live('debt')),payments=filtered(live('payment'));
    return heading('Fiados y abonos','Cada pago conserva su fecha, responsable y saldo resultante.')+`<div class="stats"><div class="stat"><span>Fiado registrado</span><strong class="value">${pesos(debts.reduce((a,r)=>a+r.payload.amount,0))}</strong></div><div class="stat"><span>Abonos en el período</span><strong class="value">${pesos(payments.reduce((a,r)=>a+r.payload.amount,0))}</strong></div><div class="stat"><span>Saldo de los fiados seleccionados</span><strong class="value">${pesos(debts.reduce((a,r)=>a+r.balance,0))}</strong></div></div><div class="card">${filters()}<h2>Cuentas pendientes y pagadas</h2>${recordList(debts)}</div>${isAdmin()?`<div class="grid"><div class="card"><h2>Registrar fiado</h2><form data-form="debt">${riderSelect()}${field('debtor','Nombre del deudor','text','','required')}${field('amount','Valor ($)','number','','required min="1" step="1"')}${field('note','Detalle de la venta','text','','maxlength="250"')}${button('Guardar fiado')}</form></div><div class="card"><h2>Abonos registrados</h2>${recordList(payments)}</div></div>`:''}`;
  }
  if(tab==='informes')return reports();
  if(tab==='equipo')return heading('Chat del equipo','Mensajes y llamadas separados de los pedidos y las cuentas.')+'<div id="team-root"></div>';
  if(tab==='admin')return administration();
  return '';
}
function stockTable(items){return `<div class="tablewrap"><table><thead><tr><th>Referencia / insumo</th><th class="right">Disponible</th></tr></thead><tbody>${items.map(n=>`<tr><td>${esc(n)}${S.inputs.includes(n)?` <span class="muted">(${S.inputs.indexOf(n)<2?'bultos':n==='Químico'?'g':n==='Bolsas'?'unidades':'unidad configurada'})</span>`:''}</td><td class="right">${decimal(S.stock[n]||0)}</td></tr>`).join('')}</tbody></table></div>`}
function reports(){
  const closures=filtered(live('close')), dispatches=filtered(live('dispatch').filter(r=>r.status!=='draft'));
  const net=closures.reduce((a,r)=>a+r.payload.net,0),credits=closures.reduce((a,r)=>a+r.payload.credits.reduce((b,c)=>b+c.amount,0),0);
  const vals=[['Valor despachado',pesos(dispatches.reduce((a,r)=>a+r.payload.total,0))],['Ventas de rutas cerradas',pesos(net)],['Fiados de rutas cerradas',pesos(credits)],['Gastos de ruta',pesos(closures.reduce((a,r)=>a+r.payload.expenses,0))],['Efectivo entregado',pesos(closures.reduce((a,r)=>a+r.payload.cash,0))],['Saldo de ruta por entregar',pesos(closures.reduce((a,r)=>a+r.balance,0))],['Entregas posteriores de ruta',pesos(filtered(live('routePayment')).reduce((a,r)=>a+r.payload.amount,0))],['Abonos a fiados',pesos(filtered(live('payment')).reduce((a,r)=>a+r.payload.amount,0))],['Otros gastos',pesos(filtered(live('expense')).reduce((a,r)=>a+r.payload.amount,0))],['Sobrantes buenos (unidades)',decimal(closures.reduce((a,r)=>a+r.payload.good.reduce((b,n)=>b+n,0),0))],['Devoluciones malas (unidades)',decimal(closures.reduce((a,r)=>a+r.payload.bad.reduce((b,n)=>b+n,0),0))]];
  return heading('Informes','Valores calculados a partir de los movimientos vigentes.')+`<div class="card">${filters()}<p class="help">Las rutas abiertas muestran valor despachado; las ventas se liquidan al cerrar cada ruta. Los abonos a fiados se muestran por separado del efectivo de ruta.</p><table><tbody>${vals.map(([k,v])=>`<tr><td>${k}</td><td class="right"><strong>${v}</strong></td></tr>`).join('')}</tbody></table><div class="actions"><button data-action="reportPrint" class="secondary">Descargar / compartir informe PDF</button><button data-action="backup" class="secondary">Descargar respaldo completo</button></div></div>`;
}
function configGrid(config){return `<div class="tablewrap"><table><thead><tr><th>Referencia</th><th>Venta $</th><th>Devolución mala $</th><th>Unidades por bulto</th><th>Bolsas por unidad</th></tr></thead><tbody>${S.products.map((n,i)=>`<tr><td>${esc(n)}</td>${[['prices','Precio de venta'],['returnPrices','Crédito por devolución mala'],['yields','Rendimiento por bulto'],['bags','Bolsas por unidad']].map(([k,label])=>`<td><input aria-label="${label}: ${esc(n)}" name="${k}${i}" type="number" min="0" step="1" value="${config[k]?.[i]||0}" required></td>`).join('')}</tr>`).join('')}</tbody></table></div>`}
function administration(){return heading('Administración','Personas, precios, producción e historial de cambios.')+`<div class="grid"><div class="card"><h2>Registrar persona</h2><form data-form="user">${field('name','Nombre','text','','required')}${field('phone','Celular','tel','','required pattern="[0-9]{7,15}"')}<div class="field"><label for="role">Permiso</label><select id="role" name="role"><option value="rider">Repartidor</option><option value="dispatcher">Despachador</option></select></div>${field('code','Código personal (mínimo 8 caracteres)','password','','required minlength="8" autocomplete="new-password"')}${button('Guardar persona')}</form></div><div class="card"><h2>Equipo registrado</h2>${S.users.filter(u=>u.role!=='admin').length?S.users.filter(u=>u.role!=='admin').map(u=>`<div class="record"><strong>${esc(u.name)}</strong><p class="record-meta">${esc(u.phone)} · ${u.role==='rider'?'Repartidor':'Despachador'}</p></div>`).join(''):empty('El equipo está vacío','Registra cada persona y entrégale su código individual.')}<h3>Logo oficial</h3><form data-form="logo"><p class="help">Carga la imagen oficial para mostrarla en la aplicación y los comprobantes.</p><div class="field"><label for="logo-file">Imagen PNG o JPG</label><input id="logo-file" name="logo" type="file" accept="image/png,image/jpeg" required></div>${button('Guardar logo')}</form></div></div><div class="card"><h2>Precios y rendimientos</h2><form data-form="settings"><div class="field"><label for="config-rider">Aplicar precios a</label><select id="config-rider" name="rider"><option value="">Precios generales y rendimientos de fábrica</option>${S.users.filter(u=>u.role==='rider').map(u=>`<option value="${u.id}">${esc(u.name)}</option>`).join('')}</select></div><p class="help">Venta y devoluciones se guardan por separado. Los rendimientos de fábrica se toman de la configuración general. Unidades significa la presentación que se despacha, no arepas individuales.</p><div id="config-grid">${configGrid(S.config)}</div>${button('Guardar configuración')}</form></div><div class="grid"><div class="card"><h2>Gasto administrativo</h2><form data-form="expense">${field('reason','Concepto','text','','required')}${field('amount','Valor ($)','number','','required min="1" step="1"')}${button('Guardar gasto')}</form><div class="actions"><button class="secondary" data-action="backup">Descargar respaldo</button></div></div><div class="card"><h2>Historial de cambios</h2>${S.audit.length?S.audit.map(a=>`<div class="audit"><strong>${esc(a.action)}</strong> · ${esc(who(a.actor))}<br><span class="muted">${esc(a.created)}</span>${JSON.parse(a.detail).reason?`<p>${esc(JSON.parse(a.detail).reason)}</p>`:''}</div>`).join(''):empty('Sin cambios','Aquí quedará la actividad administrativa.')}</div></div>`}
function bindForms(){
  document.querySelectorAll('form[data-form]').forEach(form=>{
    if(form.dataset.bound==='yes')return;
    form.dataset.bound='yes';
    form.dataset.key=id();
    form.addEventListener('input',()=>{form.dataset.key=id();const total=form.querySelector('[data-qty-total]');if(total)total.textContent=decimal(readQty(form,'qty').reduce((a,n)=>a+n,0))});
    if(form.dataset.form==='draft')bindDraft(form);
    if(form.dataset.form==='ai-generate'&&!S.aiEnabled)form.querySelector('[type=submit]').disabled=true;
    if(form.dataset.form==='close'){form.addEventListener('input',()=>updateRoute(form));updateRoute(form)}
    form.addEventListener('submit',event=>{event.preventDefault();form.dataset.form==='draft'?saveDraft(form).then(()=>refresh()).catch(error=>notify(error.message)):submit(form)});
  });
  const selector=document.querySelector('#config-rider');
  if(selector)selector.addEventListener('change',()=>{document.querySelector('#config-grid').innerHTML=configGrid(selector.value?S.pricesByRider[selector.value]&&Object.keys(S.pricesByRider[selector.value]).length?S.pricesByRider[selector.value]:S.config:S.config)});
  const inputSelect=document.querySelector('select#item');
  if(inputSelect)inputSelect.addEventListener('change',()=>{document.querySelector('#unit').value=S.inputs.indexOf(inputSelect.value)<2?'bultos':inputSelect.value==='Químico'?'gramos':inputSelect.value==='Bolsas'?'unidades':'kg'});
  document.querySelectorAll('[data-qty-total]').forEach(el=>el.textContent=decimal(readQty(el.closest('form'),'qty').reduce((a,n)=>a+n,0)));
}
function readQty(form,prefix){return S.products.map((_,i)=>Number(form.elements[prefix+i]?.value||0))}
export function bindDraft(form){
  const select=form.elements.rider;
  const load=()=>{
    const owner=select?select.value:S.user.id;
    const record=live('dispatch').find(r=>r.owner===owner&&r.status==='draft');
    form.draftVersion=record?.payload.version||0;form.draftOwner=owner;form.draftPending=null;
    S.products.forEach((_,i)=>form.elements['qty'+i].value=record?.payload.qty[i]||0);
    form.querySelector('.form-message').textContent=record?'Borrador recuperado. Los cambios se guardan automáticamente.':'Los cambios se guardan automáticamente al elegir un repartidor.';
  };
  load();select?.addEventListener('change',load);
  form.addEventListener('input',event=>{
    if(event.target===select)return;
    form.draftDirty=true;if(select&&select.value)select.disabled=true;
    form.querySelector('.form-message').textContent='Cambios pendientes de guardar…';
    clearTimeout(form.draftTimer);form.draftTimer=setTimeout(()=>saveDraft(form).catch(error=>notify(error.message)),800);
  });
}
export async function saveDraft(form){
  clearTimeout(form.draftTimer);
  if(form.draftSaving){await form.draftSaving;if(form.draftDirty)return saveDraft(form);return}
  if(!form.draftDirty)return;
  const select=form.elements.rider,msg=form.querySelector('.form-message');
  form.draftSaving=(async()=>{
    while(form.draftDirty){
      if(!form.draftOwner)throw new Error('Selecciona primero un repartidor.');
      if(!form.reportValidity())throw new Error('Revisa las cantidades del borrador.');
      // Preserve the same request after an uncertain network outcome.
      form.draftPending ||= {key:id(),payload:{rider:form.draftOwner,qty:readQty(form,'qty'),expected:form.draftVersion}};
      msg.textContent='Guardando borrador…';
      const result=await api('/api/action/draft',form.draftPending);
      const sent=form.draftPending.payload.qty;
      form.draftVersion=result.detail.version;form.draftPending=null;
      const record={id:result.id,kind:'dispatch',owner:form.draftOwner,date:S.today,status:'draft',payload:result.detail};
      const index=S.records.findIndex(r=>r.id===result.id);if(index<0)S.records.push(record);else S.records[index]=record;
      form.draftDirty=JSON.stringify(sent)!==JSON.stringify(readQty(form,'qty'));
    }
    msg.textContent='Borrador guardado. Puedes cambiar de sección.';
    if(select)select.disabled=false;
  })();
  try{await form.draftSaving}catch(error){msg.innerHTML=`<p class="error">${esc(error.message)} Tus cantidades siguen en el formulario. Puedes reintentar con «Guardar borrador».</p><button type="button" class="secondary small" data-action="reloadDraft">Descartar cambios y cargar el borrador guardado</button>`;throw error}finally{form.draftSaving=null}
}
async function flushDraft(){const form=document.querySelector('form[data-form="draft"]');if(form)await saveDraft(form)}
function updateRoute(form){
  let summary=form.querySelector('[data-route-summary]');
  if(!summary){summary=document.createElement('div');summary.dataset.routeSummary='';summary.className='total';form.querySelector('.form-message').before(summary)}
  const credits=[...form.querySelectorAll('.credit-row')].map(row=>({debtor:row.querySelector('[data-debtor]').value,amount:Number(row.querySelector('[data-credit]').value)}));
  const result=routePreview(byId(form.dataset.id).payload,{good:readQty(form,'good'),bad:readQty(form,'bad'),expenses:Number(form.elements.expenses.value),cash:Number(form.elements.cash.value),credits});
  summary.innerHTML=`<div>Valor de ruta: <strong>${pesos(result.net)}</strong><br>Fiados: ${pesos(result.creditTotal)}<br>Efectivo por entregar: ${pesos(result.due)}<br>Saldo pendiente: <strong>${pesos(result.balance)}</strong>${result.errors.map(e=>`<p class="error">${esc(e)}</p>`).join('')}</div>`;
  form.querySelector('[type=submit]').disabled=!!result.errors.length;
}
async function submit(form){
  if(form.dataset.busy==='yes')return;
  if(form.dataset.saved){await savedPdf(form.dataset.saved,form.dataset.pdfTitle,!!S.logo,openModal,notify);return;}
  const kind=form.dataset.form,p=Object.fromEntries(new FormData(form).entries()),submitButton=form.querySelector('[type=submit]'),msg=form.querySelector('.form-message');
  form.dataset.busy='yes';submitButton.disabled=true;const label=submitButton.textContent;submitButton.textContent='Guardando…';msg.innerHTML='';
  try{
    let result;
    if(kind==='login'||kind==='setup')result=await api('/api/'+kind,p);
    else if(kind==='ai-generate'){
      const preview=await api('/api/ai/preview',{question:p.question,consent:p.consent==='on'});
      openModal(aiReview(preview));document.querySelector('form[data-form="ai-save"]').aiPreview=preview;
      return;
    }
    else{
      if(kind==='ai-save'){delete p.consent;p.preview=form.aiPreview;}
      if(['order','draft','production'].includes(kind))p.qty=readQty(form,'qty');
      if(kind==='production')p.extras={'Harina':Number(p.flour),'Sal':Number(p.salt)};
      if(kind==='settings')for(const k of ['prices','returnPrices','yields','bags'])p[k]=readQty(form,k);
      if(kind==='close'){
        p.id=form.dataset.id;for(const k of ['good','bad','changes'])p[k]=readQty(form,k);
        p.credits=[...form.querySelectorAll('.credit-row')].map(row=>({debtor:row.querySelector('[data-debtor]').value,amount:Number(row.querySelector('[data-credit]').value)})).filter(c=>c.debtor||c.amount);
      }
      if(kind==='payment'||kind==='routePayment')p.id=form.dataset.id;
      if(kind==='void'||kind==='settle')p.id=form.dataset.id;
      if(kind==='confirm'){p.id=form.dataset.id;p.expected=Number(form.dataset.version);p.quote=form.dataset.quote;}
      if(kind==='logo'){
        const file=form.elements.logo.files[0];if(file.size>1_000_000)throw new Error('El logo debe pesar máximo 1 MB.');
        p.value=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('No se pudo leer la imagen.'));reader.readAsDataURL(file)});
        delete p.logo;
      }
      result=await api('/api/action/'+kind,{key:form.dataset.key,payload:p});
    }
    const saved={kind,result,day:p.date,name:p.name,qty:p.qty};
    const generatesPdf=S.user&&['order','production','input','confirm','close','debt','payment','routePayment','expense','ai-save'].includes(kind);
    if(generatesPdf){form.dataset.saved=result.id;form.dataset.pdfTitle=kind==='confirm'?'Comprobante de despacho':kind==='ai-save'?'Informe con Gemini':labels[kind];}
    try{await refresh()}catch{notify('Registro guardado. No se pudo actualizar la lista; vuelve a entrar a esta sección.')}
    modal.close();notify(result.message);
    if(kind==='order')openModal(`<h2>Pedido guardado</h2><div class="success"><strong>${esc(saved.name)}</strong><br>Entrega: ${esc(saved.day)}<br>Pedido: ${esc(result.id)}</div>${quantityTable({qty:saved.qty})}<p>La fábrica ya tiene tu pedido.</p>`);
    if(kind==='setup'||kind==='login'){tab='pedidos';render()}
    if(generatesPdf){
      await savedPdf(result.id,form.dataset.pdfTitle,!!S.logo,openModal,notify);
    }
  }catch(error){msg.innerHTML=`<div class="error">${esc(error.message)}</div>`;}
  finally{form.dataset.busy='no';submitButton.disabled=false;submitButton.textContent=label;}
}
function openModal(html){document.querySelector('#modal-body').innerHTML=html;if(!modal.open)modal.showModal();bindForms()}
export function aiReview(preview){
  const p=preview.document;
  return `<h2>Revisa el resumen de Gemini</h2><p>Generado: ${esc(p.generatedDate)}</p><p>Consulta: ${esc(p.question)}</p><div class="ai-answer">${esc(p.answer)}</div><p class="help">Este informe utiliza una copia de los datos al momento de generarlo. Las recomendaciones necesitan tu revisión.</p><form data-form="ai-save"><label class="check-line"><input type="checkbox" required> Revisé el resumen y quiero guardarlo.</label>${button('Guardar y generar PDF')}</form>`;
}
function routeForm(r){return `<h2>Cierre de ruta</h2><p>${esc(who(r.owner))} · ${r.date} · Despachado: <strong>${pesos(r.payload.total)}</strong></p><form data-form="close" data-id="${r.id}"><details open><summary>Sobrantes buenos</summary><p class="help">Vuelven al inventario y se descuentan de la cuenta de esta ruta.</p>${qtyInputs('good')}</details><details><summary>Devoluciones malas</summary><p class="help">No vuelven al inventario. Se aplica el precio de devolución configurado al confirmar el despacho.</p>${qtyInputs('bad')}</details><details><summary>Cambios / reposiciones</summary><p class="help">Producto adicional que sale para reponer. Descuenta inventario sin generar otra venta.</p>${qtyInputs('changes')}</details><h3>Fiados de la ruta</h3><div id="credit-rows"></div><button type="button" class="secondary small" data-action="addCredit">Agregar fiado</button><hr><div class="row">${field('expenses','Gastos de ruta ($)','number',0,'required min="0" step="1"')}${field('cash','Efectivo entregado ($)','number',0,'required min="0" step="1"')}</div>${field('expenseReason','Concepto de los gastos','text','','maxlength="250"')}<p class="help">El cierre quedará pendiente de revisión en Administración. Los sobrantes buenos, las reposiciones y los fiados se registran una sola vez.</p>${button('Enviar cierre a Administración')}</form>`}
export function dispatchReview(quote){
  const shortages=quote.shortages.map(s=>`<li>${esc(s.item)}: faltan ${decimal(s.missing)}</li>`).join('');
  const returns=S.products.map((name,i)=>quote.qty[i]?`<tr><td>${esc(name)}</td><td class="right">${pesos(quote.returnPrices[i])}</td></tr>`:'').join('');
  return `<h2>Revisa tu despacho</h2><p>${esc(who(quote.owner))}</p>${quantityTable(quote)}<div class="total"><span>Total del despacho</span><strong>${pesos(quote.total)}</strong></div><details><summary>Precios de devoluciones malas</summary><div class="tablewrap"><table><thead><tr><th>Referencia</th><th>Precio por devolución</th></tr></thead><tbody>${returns}</tbody></table></div></details>${shortages?`<div class="error"><strong>Falta producto en inventario</strong><ul>${shortages}</ul><p>Registra la producción y vuelve a revisar el despacho.</p></div>`:`<form data-form="confirm" data-id="${esc(quote.id)}" data-version="${quote.version}" data-quote="${esc(quote.token)}"><p class="help">Confirmar descuenta inventario y fija las cantidades y precios de este despacho.</p><label class="check-line"><input type="checkbox" required> Revisé las cantidades, los precios y el total.</label>${button('Confirmar despacho')}</form>`}<button class="secondary full-width" data-action="reviewDispatch" data-id="${esc(quote.id)}">Actualizar esta revisión</button>`;
}
function quantityTable(p){
  if(!p.qty)return '';
  return `<div class="tablewrap"><table><thead><tr><th>Referencia</th><th class="right">Cantidad</th>${p.prices?'<th class="right">Precio</th><th class="right">Subtotal</th>':''}</tr></thead><tbody>${S.products.map((n,i)=>p.qty[i]?`<tr><td>${esc(n)}</td><td class="right">${p.qty[i]}</td>${p.prices?`<td class="right">${pesos(p.prices[i])}</td><td class="right">${pesos(p.prices[i]*p.qty[i])}</td>`:''}</tr>`:'').join('')}</tbody></table></div>`;
}
function details(r){
  const p=r.payload;
  let body=`<p>${labels[r.kind]} · ${r.date}<br>${esc(p.name||who(r.owner))}<br>Estado: ${statuses[r.status]}</p>${quantityTable(p)}`;
  if(r.kind==='aiReport')body+=`<p>${esc(p.question)}</p><div class="ai-answer">${esc(p.answer)}</div><p class="help">Generado con los datos disponibles el ${esc(p.generatedDate)}. No modifica las cuentas.</p>`;
  const moneyFields={total:'Subtotal despachado',amount:'Valor',net:'Venta liquidada',expenses:'Gastos de ruta',cash:'Efectivo entregado',due:'Corresponde entregar',balance:'Saldo resultante',cost:'Costo total'};
  for(const [key,label] of Object.entries(moneyFields))if(p[key]!==undefined)body+=`<div class="total"><span>${label}</span><strong>${pesos(p[key])}</strong></div>`;
  if(r.kind==='debt')body+=`<p>Deudor: <strong>${esc(p.debtor)}</strong></p><div class="total"><span>Saldo pendiente actual</span><strong>${pesos(r.balance)}</strong></div><h3>Abonos</h3>${live('payment').filter(a=>a.payload.debt_id===r.id).map(a=>`<p>${a.date} · ${pesos(a.payload.amount)} · saldo tras abono: ${pesos(a.payload.balance)}</p>`).join('')||'<p>No hay abonos registrados.</p>'}`;
  if(r.kind==='close'){
    body+=`<div class="total"><span>Saldo pendiente actual de la ruta</span><strong>${pesos(r.balance)}</strong></div>`;
    body+=`<h3>Devoluciones y cambios</h3><table><thead><tr><th>Referencia</th><th>Buenos</th><th>Malos</th><th>Cambios</th></tr></thead><tbody>${S.products.map((n,i)=>`<tr><td>${esc(n)}</td><td>${p.good[i]}</td><td>${p.bad[i]}</td><td>${p.changes[i]}</td></tr>`).join('')}</tbody></table><h3>Fiados</h3>${p.credits.map(c=>`<p>${esc(c.debtor)}: ${pesos(c.amount)}</p>`).join('')||'<p>Sin fiados.</p>'}`;
  }
  if(r.kind==='production')body+=`<p>Maíz: ${decimal(p.bultos)} bultos · Químico: ${decimal(p.chemicalGrams)} g (${decimal(p.bultos)} × 400 g).</p><p>Insumos: ${Object.entries(p.consumption).map(([k,v])=>`${esc(k)}: ${decimal(v)}`).join(' · ')}</p>`;
  if(r.kind==='input')body+=`<p>${esc(p.item)}: ${decimal(p.qty)} ${esc(p.unit)}</p>`;
  for(const key of ['debtor','reason','expenseReason','note','reviewNote'])if(p[key])body+=`<p>${esc(p[key])}</p>`;
  body+=`<p class="help">Registro: ${r.id} · Guardado: ${esc(r.created)}</p>`;
  return body;
}
function printDocument(title,body){
  modal.close();
  const logo=S.logo?`<img class="print-logo" src="${esc(S.logo)}" alt="Logo oficial">`:'<p>Arepas La Mañanera</p>';
  document.querySelector('#receipt').innerHTML=`<table><thead><tr><td><div class="print-header"><div><h1 class="print-title">${esc(title)}</h1><p>Arepas La Mañanera · ${esc(S.today)}</p></div>${logo}</div></td></tr></thead><tbody><tr><td>${body}</td></tr></tbody></table>`;
  requestAnimationFrame(()=>window.print());
}
async function simpleAction(action,rid,extra={}){await api('/api/action/'+action,{key:id(),payload:{id:rid,...extra}});await refresh();notify('Guardado correctamente.')}
app.addEventListener('change',async event=>{if(event.target.dataset.filter){try{await flushDraft();if(event.target.dataset.filter==='date')filterDate=event.target.value;else filterRider=event.target.value;render()}catch(error){notify(error.message)}}});
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.classList.contains('close-modal')){modal.close();return}
  if(button.dataset.tab){try{await flushDraft();tab=button.dataset.tab;filterDate='';filterRider='';await refresh()}catch(error){notify(error.message)}return}
  const action=button.dataset.action,r=byId(button.dataset.id);if(!action)return;
  if(button.disabled)return;
  try{
    if(action==='reloadDraft'){
      if(confirm('¿Descartar las cantidades sin guardar y cargar el borrador más reciente?'))await refresh();return;
    }
    await flushDraft();
    if(action==='logout'){await api('/api/logout',{});tab='pedidos';await refresh()}
    if(action==='clearFilters'){filterDate='';filterRider='';render()}
    if(action==='detail')openModal(`<h2>${labels[r.kind]}</h2>${details(r)}`);
    if(action==='print'){button.disabled=true;await openPdf('/api/pdf/'+r.id,r.kind==='debt'?'Estado de cuenta':labels[r.kind],openModal,notify)}
    if(action==='route')openModal(routeForm(r));
    if(action==='payment')openModal(`<h2>Registrar abono</h2><p>${esc(r.payload.debtor)} · saldo: <strong>${pesos(r.balance)}</strong></p><form data-form="payment" data-id="${r.id}">${field('amount','Valor del abono ($)','number','','required min="1" step="1" max="'+r.balance+'"')}${button('Guardar abono')}</form>`);
    if(action==='routePayment')openModal(`<h2>Entrega de saldo de ruta</h2><p>${esc(who(r.owner))} · saldo: <strong>${pesos(r.balance)}</strong></p><form data-form="routePayment" data-id="${r.id}">${field('amount','Efectivo recibido ($)','number','','required min="1" step="1" max="'+r.balance+'"')}${button('Guardar entrega')}</form>`);
    if(action==='confirm'||action==='reviewDispatch'){button.disabled=true;const result=await api('/api/action/preview-dispatch',{key:id(),payload:{id:r.id}});openModal(dispatchReview(result.detail))}
    if(action==='void'||action==='settle')openModal(`<h2>${action==='void'?'Anular registro':'Revisar cierre'}</h2>${details(r)}<form data-form="${action}" data-id="${r.id}">${field('reason',action==='void'?'Motivo de la anulación':'Observaciones de la revisión','text','','required maxlength="250"')}<p class="help">${action==='void'?'El original quedará en el historial. Después puedes registrar los datos correctos.':'La revisión conserva el saldo pendiente y los fiados por cobrar.'}</p><label><input type="checkbox" required> Revisé los datos y confirmo esta acción.</label>${button(action==='void'?'Confirmar anulación':'Guardar revisión')}</form>`);
    if(action==='addCredit'){const row=document.createElement('div');row.className='credit-row';row.innerHTML='<input data-debtor placeholder="Nombre del deudor" aria-label="Nombre del deudor" maxlength="100"><input data-credit type="number" min="1" step="1" placeholder="Valor $" aria-label="Valor del fiado"><button type="button" data-action="removeCredit" aria-label="Quitar fiado">×</button>';document.querySelector('#credit-rows').append(row);row.querySelector('input').focus()}
    if(action==='removeCredit'){const form=button.closest('form');button.closest('.credit-row').remove();updateRoute(form)}
    if(action==='reportPrint'){button.disabled=true;await openPdf('/api/report.pdf?'+new URLSearchParams({date:filterDate,rider:filterRider}),'Informe de movimientos',openModal,notify)}
    if(action==='backup'){button.disabled=true;await downloadBackup(notify)}
    if(action==='install'&&installPrompt){await installPrompt.prompt();installPrompt=null;render()}
  }catch(error){notify(error.message)}finally{button.disabled=false}
});
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;});
window.addEventListener('online',()=>notify('Volvió la conexión. Puedes volver a intentar guardar.'));
window.addEventListener('offline',()=>notify('Sin conexión. No cierres los formularios sin guardar.'));
window.addEventListener('beforeunload',event=>{if(document.querySelector('form[data-form="draft"]')?.draftDirty){event.preventDefault();event.returnValue=''}});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
refresh().catch(error=>{app.innerHTML=`<main class="boot"><h1>Arepas La Mañanera</h1><div class="error">${esc(error.message)}</div><p>La aplicación necesita su servidor para guardar y consultar los registros.</p><button id="retry">Volver a intentar</button></main>`;document.querySelector('#retry').onclick=()=>location.reload()});
