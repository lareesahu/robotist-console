// The homepage's scroll state and mobile navigation behavior, shared by GRN flows.
(() => {
  const nav = document.getElementById('mainNav');
  const button = nav?.querySelector('.nav-hamburger');
  const links = nav?.querySelector('.nav-links');
  if (!nav || !button || !links) return;
  const scroll = () => nav.classList.toggle('scrolled', window.scrollY > 40);
  scroll(); window.addEventListener('scroll', scroll, {passive:true});
  const close = () => {links.classList.remove('open');button.classList.remove('active');button.setAttribute('aria-expanded','false');};
  button.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    button.classList.toggle('active', open);button.setAttribute('aria-expanded',String(open));
    if (open) links.querySelector('a')?.focus();
  });
  links.querySelectorAll('a').forEach(link => link.addEventListener('click',close));
  nav.addEventListener('keydown', event => {
    if(event.key==='Escape'){close();button.focus();return;}
    if(event.key!=='Tab'||!links.classList.contains('open')) return;
    const items=[...links.querySelectorAll('a')];
    if(event.target===items[0]&&event.shiftKey){event.preventDefault();button.focus();}
    else if(event.target===items.at(-1)&&!event.shiftKey){event.preventDefault();button.focus();}
    else if(event.target===button){event.preventDefault();(event.shiftKey?items.at(-1):items[0]).focus();}
  });
  nav.addEventListener('focusout', event => {if(!nav.contains(event.relatedTarget)) close();});
  window.addEventListener('resize', close);
})();
