(() => {
  const form = document.querySelector('#grn-application');
  if (!form) return;
  const first = form.querySelector('[data-step="1"]');
  const second = form.querySelector('[data-step="2"]');
  const next = form.querySelector('#application-next');
  const back = form.querySelector('#application-back');
  const progress = form.querySelector('.form-progress');
  const firstInvalid = () => [...first.querySelectorAll('input,select')].find(el => !el.checkValidity());
  function show(step, focus = true) {
    first.hidden = step !== 1;
    second.hidden = step !== 2;
    progress.textContent = step === 1 ? '01 / About you' : '02 / Your contribution';
    if (focus) (step === 1 ? first : second).querySelector('input,textarea,select').focus({preventScroll:true});
  }
  next.hidden = back.hidden = false;
  next.addEventListener('click', () => {
    const invalid = firstInvalid();
    if (invalid) return invalid.reportValidity();
    show(2);
  });
  back.addEventListener('click', () => show(1));
  form.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !first.hidden && event.target.tagName === 'INPUT') {
      event.preventDefault(); next.click();
    }
  });
  form.addEventListener('invalid', event => {
    if (first.contains(event.target)) show(1, false);
    const details = event.target.closest('details');
    if (details) details.open = true;
  }, true);
  show(document.querySelector('.hero-application .error') && !firstInvalid() ? 2 : 1, false);
})();
