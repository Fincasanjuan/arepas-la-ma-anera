export const labels={order:'Pedido',dispatch:'Despacho',close:'Cierre de ruta',production:'Producción',input:'Entrada de insumos',debt:'Fiado',payment:'Abono',routePayment:'Entrega de saldo de ruta',expense:'Gasto',aiReport:'Informe con Gemini'};
export const statuses={draft:'Borrador',confirmed:'Confirmado',closed:'Ruta cerrada',pending:'Pendiente de revisión',reviewed:'Revisado',void:'Anulado'};
export const pesos=value=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Number(value)||0);
export const decimal=value=>new Intl.NumberFormat('es-CO',{maximumFractionDigits:3}).format(Number(value)||0);
export function routePreview(dispatch,{good,bad,expenses,cash,credits}){
  const errors=[];
  if([...good,...bad,expenses,cash,...credits.map(c=>c.amount)].some(n=>!Number.isFinite(n)||n<0))errors.push('Revisa los valores: deben ser positivos o cero.');
  if([...good,...bad].some(n=>!Number.isInteger(n)))errors.push('Las devoluciones deben ser cantidades enteras.');
  if(good.some((q,i)=>q+bad[i]>dispatch.qty[i]))errors.push('Las devoluciones superan el despacho.');
  if(credits.some(c=>!c.debtor.trim()))errors.push('Escribe el nombre de cada deudor.');
  const creditTotal=credits.reduce((s,c)=>s+c.amount,0);
  const net=dispatch.total-good.reduce((s,q,i)=>s+q*dispatch.prices[i]+bad[i]*dispatch.returnPrices[i],0);
  const due=net-expenses-creditTotal,balance=due-cash;
  if(due<0)errors.push('Los gastos y fiados superan el valor de la ruta.');
  if(balance<0)errors.push('El efectivo supera lo que corresponde entregar.');
  return {net,creditTotal,due,balance,errors};
}
export function productionPlan(orders,products,config,inventory){
  const totals=products.map((_,i)=>orders.reduce((sum,r)=>sum+(r.payload.qty?.[i]||0),0));
  const missing=totals.map((n,i)=>Math.max(0,n-(inventory[products[i]]||0)));
  const unconfigured=missing.some((n,i)=>n&&!config.yields?.[i]);
  const bultos=unconfigured?null:missing.reduce((sum,n,i)=>sum+(n?n/config.yields[i]:0),0);
  return {totals,missing,bultos,chemicalGrams:bultos===null?null:bultos*400};
}
