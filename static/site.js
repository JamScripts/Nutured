/* Progressive enhancement only: discovery, categories, and details work without JS. */
document.documentElement.classList.remove('no-js');
const navToggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('#site-nav');
function closeNav(returnFocus = false) {
  nav?.classList.remove('is-open');
  navToggle?.setAttribute('aria-expanded', 'false');
  navToggle?.setAttribute('aria-label', 'Open navigation');
  if (returnFocus) navToggle?.focus();
}
navToggle?.addEventListener('click', () => {
  const open = navToggle.getAttribute('aria-expanded') !== 'true';
  navToggle.setAttribute('aria-expanded', String(open));
  navToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  nav.classList.toggle('is-open', open);
});
nav?.addEventListener('click', event => { if (event.target.closest('a')) closeNav(); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && navToggle?.getAttribute('aria-expanded') === 'true') closeNav(true);
});
matchMedia('(min-width: 851px)').addEventListener('change', () => closeNav());

const agentDialog = document.querySelector('#agent-dialog');
const launcher = document.querySelector('[data-open-agent]');
launcher?.addEventListener('click', () => agentDialog.showModal());
agentDialog?.addEventListener('keydown', event => {
  if (event.key !== 'Tab') return;
  const controls = [...agentDialog.querySelectorAll('button, a[href]')];
  const first = controls[0], last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault(); last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus();
  }
});
document.querySelector('[data-close-agent]')?.addEventListener('click', () => agentDialog.close());
agentDialog?.addEventListener('close', () => launcher.focus());
agentDialog?.addEventListener('click', event => {
  if (event.target !== agentDialog) return;
  const bounds = agentDialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) agentDialog.close();
});

document.querySelector('[data-discovery]')?.addEventListener('submit', () => {
  document.querySelector('.loading-state').hidden = false;
});
// A full-page GET preserves browser history and selected controls. Focus the
// result heading after navigation so keyboard/screen-reader users find updates.
function restorePageState() {
  document.querySelectorAll('.loading-state').forEach(node => { node.hidden = true; });
  if (['#results', '#just-for-you', '#kits'].includes(location.hash)) {
    document.querySelector(location.hash)?.focus({ preventScroll: true });
  }
}
window.addEventListener('pageshow', restorePageState);
restorePageState();
