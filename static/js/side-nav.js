/**
 * Mobile / narrow: toggle side navigation overlay.
 * Desktop: navigation uses CSS :hover on .d365-nav-host (auto-hide rail).
 */
(function () {
  const host = document.getElementById('d365-nav-host');
  const fab = document.getElementById('d365-nav-fab');
  const backdrop = document.getElementById('d365-nav-backdrop');

  if (!host || !fab) return;

  const mq = window.matchMedia('(max-width: 768px)');

  function setOpen(open) {
    host.classList.toggle('is-open', open);
    fab.setAttribute('aria-expanded', open ? 'true' : 'false');
    fab.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    if (backdrop) {
      if (open) backdrop.removeAttribute('hidden');
      else backdrop.setAttribute('hidden', '');
    }
    document.body.classList.toggle('d365-nav-is-open', open);
  }

  function close() {
    setOpen(false);
  }

  function toggle() {
    setOpen(!host.classList.contains('is-open'));
  }

  fab.addEventListener('click', function () {
    if (!mq.matches) return;
    toggle();
  });

  backdrop?.addEventListener('click', close);

  mq.addEventListener('change', function (e) {
    if (!e.matches) close();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && mq.matches) close();
  });
})();
