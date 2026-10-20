const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/alma_duplicate/ui/static/continuum-choice.js', 'utf8');
function fixture(selected, confirmed) {
  const control = checked => ({checked, handlers: {}, addEventListener(event, fn) { this.handlers[event] = fn; }});
  const choice = control(selected), declaration = control(confirmed), fallback = {}, note = {};
  const elements = [choice, declaration, fallback, note];
  let index = 0;
  const form = {querySelector() { return elements[index++]; }, addEventListener() {}};
  const window = {};
  vm.runInNewContext(source, {window, setTimeout});
  window.initializeContinuumChoice(form);
  return {choice, declaration, fallback, note};
}
test('only a deliberate continuum selection confirms bandwidth; deselection removes confirmation', () => {
  const {choice, declaration, fallback, note} = fixture(false, false);
  assert.equal(declaration.checked, false);
  assert.equal(fallback.hidden, true);
  assert.equal(note.hidden, false);
  choice.checked = true;
  choice.handlers.change();
  assert.equal(declaration.checked, true);
  choice.checked = false;
  choice.handlers.change();
  assert.equal(declaration.checked, false);
});
test('legacy unconfirmed selection is not silently upgraded', () => {
  const {declaration, fallback} = fixture(true, false);
  assert.equal(declaration.checked, false);
  assert.equal(fallback.hidden, false);
  declaration.checked = true;
  declaration.handlers.change();
  assert.equal(fallback.hidden, true);
});
test('initialization preserves declarations including retained unselected evidence', () => {
  for (const selected of [false, true]) {
    const {declaration, fallback} = fixture(selected, true);
    assert.equal(declaration.checked, true);
    assert.equal(fallback.hidden, true);
  }
});
