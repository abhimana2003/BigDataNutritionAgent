(() => {
  const pages = [
    document.getElementById('page-1'),
    document.getElementById('page-2'),
    document.getElementById('page-3')
  ];
  const pageIndexEl = document.getElementById('pageIndex');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  let idx = 0;

  function show(i){
    idx = (i + pages.length) % pages.length;
    pages.forEach((p, j) => p.classList.toggle('hidden', j !== idx));
    pageIndexEl.textContent = idx + 1;
  }

  prevBtn.addEventListener('click', () => show(idx - 1));
  nextBtn.addEventListener('click', () => show(idx + 1));

  document.addEventListener('keydown', (e) => {
    if(e.key === 'ArrowLeft') show(idx - 1);
    if(e.key === 'ArrowRight') show(idx + 1);
  });

  // allow clicking actions inside phone to advance
  document.querySelectorAll('.phone .action').forEach(btn => {
    btn.addEventListener('click', () => show(idx + 1));
  });

  // init
  show(0);
})();
