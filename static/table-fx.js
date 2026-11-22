// Small effects on the game table that must survive the table being redrawn after every move:
// - the explanation pop-up for special cards (click a card on the table, or the "?" on a card in your hand),
// - the card you receive from the Juggler, shown in the middle of the screen for a moment.
// The texts come from the server (views/table.py), so this file contains no game rules.

let cardInfo = {};

function kindOf(card) {
  const art = [...card.classList].find(name => name.startsWith('art-'));
  return art ? art.slice(4) : null;
}

function closePopup() {
  document.querySelector('.card-popup')?.remove();
}

function showInfo(kind, card) {
  const info = cardInfo[kind];
  if (!info) return;
  closePopup();
  const popup = document.createElement('div');
  popup.className = 'card-popup';
  popup.setAttribute('role', 'dialog');
  popup.setAttribute('aria-label', info.name);
  const panel = document.createElement('div');
  panel.className = 'card-popup-panel';
  const face = card.cloneNode(true);
  face.className = face.className.replace(/card--\w+/, 'card--lg');
  face.querySelector('.card-info')?.remove();
  face.removeAttribute('style');
  const text = document.createElement('div');
  text.className = 'card-popup-text';
  const title = document.createElement('h2');
  title.textContent = info.name;
  const body = document.createElement('p');
  body.textContent = info.text;
  const hint = document.createElement('span');
  hint.className = 'card-popup-close';
  hint.textContent = 'Tap anywhere to close';
  text.append(title, body, hint);
  panel.append(face, text);
  popup.append(panel);
  popup.addEventListener('click', closePopup);
  document.body.append(popup);
}

function onClick(event) {
  // The "?" on a card in the hand: explain the card instead of playing it.
  const button = event.target.closest('.card-info');
  if (button) {
    event.preventDefault();
    event.stopPropagation();
    const card = button.closest('.hcard')?.querySelector('.card');
    if (card) showInfo(button.dataset.kind, card);
    return;
  }
  // Special cards lying on the table (played cards, trump card, cards seen in round 1).
  const card = event.target.closest('.board .card.special-face');
  if (card) { showInfo(kindOf(card), card); return; }
  // Phone: tapping a card you cannot play right now makes it bigger, a second tap makes it small again.
  const held = event.target.closest('.hcard:not(.playable)');
  if (held && matchMedia('(pointer: coarse)').matches) {
    const open = held.classList.contains('peek');
    document.querySelectorAll('.hcard.peek').forEach(e => e.classList.remove('peek'));
    if (!open) held.classList.add('peek');
  }
}

export function install(info) {
  cardInfo = info;
  if (window.prophecyFxInstalled) return;
  window.prophecyFxInstalled = true;
  // Capture phase: runs before the click handler of the hand card, so "?" never plays the card.
  document.addEventListener('click', onClick, true);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closePopup(); });
}

export function received(cardHtml, text) {
  document.querySelector('.received-pop')?.remove();
  const pop = document.createElement('div');
  pop.className = 'received-pop';
  pop.setAttribute('role', 'status');
  pop.innerHTML = cardHtml;
  const label = document.createElement('span');
  label.className = 'received-text';
  label.textContent = text;
  pop.append(label);
  document.body.append(pop);
  setTimeout(() => pop.remove(), 2800);
}
