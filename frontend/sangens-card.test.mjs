/** Проверки настоящей карточки; служба HA заменяет внешний сервер. */
import {test, beforeEach, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {Window} from 'happy-dom';
const window = new Window({url:'http://localhost:8123/'});
for (const key of ['document','HTMLElement','customElements','CustomEvent','Event','IntersectionObserver']) globalThis[key] = window[key];
globalThis.window = window;
globalThis.matchMedia = () => ({matches:false, addEventListener(){}, removeEventListener(){}});
await import('../custom_components/sangens/frontend/sangens-card.js');
let card, calls;
const entity = (state='heat', allowed=true) => ({state, attributes:{friendly_name:'Сауна',current_temperature:28.7, temperature:81,stone_temperature:78,control_allowed:allowed,limits_known:true,min_temp:40,max_temp:100,hvac_action:'heating'}});
function update(state='heat', allowed=true){card.hass={states:{'climate.sauna':entity(state,allowed)},callService:async(...args)=>calls.push(args)};}
beforeEach(()=>{ calls=[];card=document.createElement('sangens-card');card.setConfig({entity:'climate.sauna',smoke_url:'/local/sangens/background.mp4'}); document.body.append(card); update(); });
afterEach(()=>card.remove());

test('температуры и состояние видны без открытия диалогов',()=>{
 assert.match(card.shadowRoot.querySelector('[data-current]').textContent,/28,7/);
 assert.match(card.shadowRoot.querySelector('[data-stone]').textContent,/78/);
 assert.equal(card.shadowRoot.querySelector('[data-status]').textContent,'Нагревает');
});
test('неизвестность не выглядит выключением или нагревом',()=>{
 update('unavailable');assert.equal(card.shadowRoot.querySelector('[data-status]').textContent,'Нет связи');
 assert.equal(card.shadowRoot.querySelector('[data-start]').disabled,true);
 assert.equal(card.shadowRoot.querySelector('video').hidden,true);
});
test('запуск требует подтверждения, выключение отдельная команда',async()=>{
 update('off');window.confirm=()=>false;card.shadowRoot.querySelector('[data-start]').click();
 await new Promise(resolve=>setTimeout(resolve,0)); assert.equal(calls.length,0);
 window.confirm=()=>true;card.shadowRoot.querySelector('[data-start]').click();
 await new Promise(resolve=>setTimeout(resolve,0));assert.deepEqual(calls[0],['climate','turn_on',{entity_id:'climate.sauna'}]);
 update();card.shadowRoot.querySelector('[data-stop]').click();await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(calls[1],['climate','turn_off',{entity_id:'climate.sauna'}]);
});
test('режим чтения запрещает команды в карточке',()=>{
 update('heat',false); assert.equal(card.shadowRoot.querySelector('[data-stop]').disabled,true);
 assert.equal(card.shadowRoot.querySelector('[data-target]').disabled,true);
 assert.match(card.shadowRoot.querySelector('[data-note]').textContent,/Только чтение/);
});
test('скрытие и уменьшение движения выключают видео',()=>{
 card._visible=false;card._update();assert.equal(card.shadowRoot.querySelector('video').hidden,true);
 card._visible=true;card._reducedMotion=true;card._update();assert.equal(card.shadowRoot.querySelector('video').hidden,true);
 update('off');assert.equal(card.shadowRoot.querySelector('video').hidden,true);
});
test('посторонние адреса и отсутствующая сущность отклоняются',()=>{
 assert.throws(()=>card.setConfig({entity:'climate.sauna',smoke_url:'https://other.test/a.mp4'}));
 assert.throws(()=>card.setConfig({entity:'climate.sauna',smoke_url:'//other.test/a.mp4'}));
 assert.throws(()=>card.setConfig({entity:'sensor.temp'}));
 card.hass={states:{}};assert.equal(card.shadowRoot.querySelector('[data-status]').textContent,'Сущность не найдена');
});
test('ошибка службы видна без подмены показаний',async()=>{
 card.hass={states:{'climate.sauna':entity()},callService:async()=>{throw new Error('Нет связи с печью');}};
 card.shadowRoot.querySelector('[data-stop]').click();await new Promise(resolve=>setTimeout(resolve,0));
 assert.match(card.shadowRoot.querySelector('[data-error]').textContent,/Нет связи с печью/);
 assert.match(card.shadowRoot.querySelector('[data-current]').textContent,/28,7/);
});
