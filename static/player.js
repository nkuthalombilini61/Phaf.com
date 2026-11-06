(function () {
  const items = [...document.querySelectorAll('#tracks li')];
  const play = document.getElementById('play'), vin = document.getElementById('vin');
  const time = document.getElementById('time'), prog = document.getElementById('prog'), note = document.getElementById('note');
  const audio = new Audio();
  let cur = 0, playing = false;
  const fm = s => Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
  function mark() { items.forEach((li, i) => li.classList.toggle('on', i === cur)); }
  function set(on) { playing = on; play.textContent = on ? '❚❚' : '▶'; vin.classList.toggle('spin', on); }
  function load(i, go) {
    cur = i; mark(); const src = items[i].dataset.src;
    if (!src) { audio.pause(); set(false); note.textContent = 'Audio for this track has not been uploaded yet.'; return; }
    note.textContent = ''; audio.src = src; if (go) audio.play().then(() => set(true)).catch(() => set(false));
  }
  items.forEach((li, i) => li.addEventListener('click', e => { if (e.target.tagName !== 'A') load(i, true); }));
  play.onclick = () => { if (playing) { audio.pause(); set(false); } else if (!audio.src) load(cur, true); else audio.play().then(() => set(true)); };
  audio.ontimeupdate = () => { time.textContent = fm(audio.currentTime) + ' / ' + fm(audio.duration || 0); prog.style.width = (audio.currentTime / (audio.duration || 1) * 100) + '%'; };
  audio.onended = () => load((cur + 1) % items.length, true);
  mark();
})();
