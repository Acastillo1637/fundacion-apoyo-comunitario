export const emptyFilters = { q:'', status:'', period:'' };
export const eventStates = { draft:'Borrador', open:'Convocatoria abierta', finished:'Finalizada', cancelled:'Cancelada' };
export const requestStates = { pending:'Pendiente', in_review:'En revisión', approved:'Aprobada', rejected:'Rechazada' };
export function operationPath(section, page, filters = emptyFilters) {
  const parameters = new URLSearchParams({page:String(page),compact:'1'});
  for (const field of ['q','status','period']) if (filters[field]) parameters.set(field, filters[field]);
  return `activities/operations/${section}/?${parameters}`;
}
