import { useEffect, useRef, useState } from 'react';
import { LogOut, ShieldCheck, UserRound } from 'lucide-react';
import { Avatar } from '../design/Overview';

export default function AccountMenu({ user, role, onProfile, onSecurity, onSignOut }) {
  const [open,setOpen]=useState(false);
  const root=useRef(null),trigger=useRef(null);
  const hovered=useRef(false);
  useEffect(()=>{if(!open)return;const outside=event=>{if(!root.current?.contains(event.target))setOpen(false);};const escape=event=>{if(event.key==='Escape'){event.preventDefault();setOpen(false);trigger.current?.focus();}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};},[open]);
  function close(){setOpen(false);}
  function choose(action){close();action?.();}
  function focusItem(last=false){const items=root.current.querySelectorAll('[role="menuitem"]');(last?items[items.length-1]:items[0])?.focus();}
  function key(event){
    if(event.key==='Escape'){event.preventDefault();close();trigger.current.focus();}
    if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
      event.preventDefault();setOpen(true);
      const items=Array.from(root.current.querySelectorAll('[role="menuitem"]'));
      const at=items.indexOf(document.activeElement);
      if(at<0){requestAnimationFrame(()=>focusItem(event.key==='ArrowUp'||event.key==='End'));return;}
      const next=event.key==='Home'?0:event.key==='End'?items.length-1:(at+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;
      items[next]?.focus();
    }
  }
  return <div className="account-menu" ref={root} onPointerEnter={event=>{if(event.pointerType==='mouse'){hovered.current=true;setOpen(true);}}} onPointerLeave={event=>{if(event.pointerType==='mouse'){hovered.current=false;close();}}}
    onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))close();}} onKeyDown={key}>
    <button ref={trigger} className="workspace-user" aria-label="Menú de cuenta" aria-haspopup="menu" aria-expanded={open} aria-controls="account-dropdown"
      onClick={()=>{setOpen(hovered.current?true:!open);hovered.current=false;}}><span><strong>{user.first_name} {user.last_name}</strong><small>{role}</small></span><Avatar name={`${user.first_name} ${user.last_name}`}/></button>
    {open&&<div className="account-dropdown" id="account-dropdown" role="menu" aria-label="Opciones de cuenta"><div className="account-menu-info"><strong>{user.first_name} {user.last_name}</strong><span>{user.email}</span><small>{(user.roles||[]).join(' · ')||role}</small></div>
      <button role="menuitem" onClick={()=>choose(onProfile)}><UserRound size={18}/>Mi cuenta</button>
      <button role="menuitem" onClick={()=>choose(onSecurity)}><ShieldCheck size={18}/>Seguridad de cuenta</button>
      <button role="menuitem" onClick={()=>choose(onSignOut)}><LogOut size={18}/>Cerrar sesión</button></div>}
  </div>;
}
