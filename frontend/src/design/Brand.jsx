export const slogan = 'Conectamos personas, multiplicamos la ayuda';
export function FoundationLogo({ large = false }) {
  return <img className={`foundation-logo ${large ? 'large' : ''}`} src="/brand/fundacion-logo.png?v=2" alt="Logo oficial de Fundación Apoyo Comunitario" width="1254" height="1254"/>;
}
