/** Общая карточка: только состояния и службы HA, без облачных учётных данных. */
class SangensCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._visible = true;
    this._pending = false;
    this._reducedMotion = false;
    this._error = '';
    // Шаблон статический: значения устройств вставляются только через textContent.
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;--sauna-accent:#f0bb79;color:var(--primary-text-color,#f7f1e9)}
        *{box-sizing:border-box}ha-card{display:block;position:relative;overflow:hidden;border-radius:28px;background:#202328;color:#f7f1e9;min-height:480px;border:1px solid #ffffff12}
        video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.32;pointer-events:none}
        [hidden]{display:none!important}.shade{position:absolute;inset:0;background:linear-gradient(180deg,#171a20a0,#1d2025e0 85%);pointer-events:none}
        .content{position:relative;padding:26px;z-index:1}header{display:flex;justify-content:space-between;align-items:center;gap:12px}
        h2{font-size:24px;line-height:1.2;margin:0;font-weight:600}button,select,input{font:inherit}button{cursor:pointer}
        .details{border:1px solid #ffffff25;border-radius:50%;width:42px;height:42px;color:inherit;background:#ffffff08;font-size:21px}
        .status{margin-top:8px;font-size:14px;color:#c5c8ce;display:flex;align-items:center;gap:7px}
        .dot{width:7px;height:7px;background:#8b9099;border-radius:50%}.active .dot{background:var(--sauna-accent);box-shadow:0 0 12px #f0bb7977}
        .measurements{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:24px 0 14px}
        .pill{background:#ffffff09;border:1px solid #ffffff12;padding:12px 15px;border-radius:16px;display:flex;flex-direction:column;gap:5px}
        .pill span{font-size:12px;color:#c5c8ce}.pill strong{font-size:21px;font-weight:500}
        .dial{width:min(100%,258px);aspect-ratio:1;margin:20px auto;display:grid;place-items:center;border:1px solid #ffffff13;border-radius:50%;position:relative;background:radial-gradient(circle at 50% 40%,#ffffff07,transparent 65%);box-shadow:inset 0 0 36px #0002}
        .dial:before{content:'';position:absolute;inset:9px;border-radius:50%;border:3px solid #ffffff14}.active .dial:before{border-color:#f0bb7966;box-shadow:0 0 24px #f0bb7910}
        .reading{text-align:center}.reading small{display:block;color:#c5c8ce;font-size:13px;margin-bottom:8px}.reading strong{font-size:clamp(52px,14vw,70px);font-weight:350;line-height:1.1;letter-spacing:-2px}.reading .target{margin-top:9px;color:#c5c8ce;font-size:14px}
        .adjust{padding:5px 2px 13px}.adjust label{display:flex;justify-content:space-between;font-size:14px;color:#d1d1d5;margin-bottom:12px}input[type=range]{width:100%;accent-color:var(--sauna-accent);height:26px;cursor:pointer}
        .actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}button.action{border:1px solid #ffffff22;border-radius:15px;padding:15px 10px;min-height:50px;color:inherit;background:#ffffff0b;font-weight:550}.action.start{background:var(--sauna-accent);color:#252322;border-color:transparent}button:disabled,select:disabled,input:disabled{opacity:.4;cursor:default}
        .advanced{margin-top:18px;border-top:1px solid #ffffff12;padding-top:14px}.advanced summary{cursor:pointer;font-size:14px;color:#d1d1d5;padding:5px 0}.advanced label{display:block;font-size:13px;margin:14px 0 7px}select{width:100%;padding:12px;color:#fff;background:#30343c;border:1px solid #ffffff25;border-radius:10px}.stone-settings{width:100%;margin-top:12px;padding:12px;border-radius:10px;border:1px solid #ffffff25;background:transparent;color:inherit}
        .note{color:#bbbfc7;font-size:12px;line-height:1.5;margin:14px 0 0}.error{color:#ffb8af;font-size:13px;line-height:1.5;margin-top:12px}button:focus-visible,summary:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--sauna-accent);outline-offset:3px}
        @media(max-width:360px){.content{padding:18px}.pill{padding:10px}.dial{width:220px}}@media(prefers-reduced-motion:reduce){video{display:none}}
      </style>
      <ha-card>
        <video muted loop playsinline preload="none" hidden aria-hidden="true"></video><div class="shade"></div>
        <div class="content"><header><div><h2 data-title>Сауна</h2><div class="status"><span class="dot"></span><span data-status aria-live="polite">Нет данных</span></div></div><button class="details" data-details title="Открыть устройство" aria-label="Открыть подробности печи">⋯</button></header>
        <div class="measurements"><div class="pill"><span>Воздух</span><strong data-air>—</strong></div><div class="pill"><span>Камни</span><strong data-stone>—</strong></div></div>
        <div class="dial"><div class="reading"><small>Температура воздуха</small><strong data-current>—</strong><div class="target" data-setpoint>Заданная: —</div></div></div>
        <div class="adjust"><label for="target"><span>Заданная температура</span><span data-range></span></label><input id="target" data-target type="range" step="1" min="0" max="0" disabled aria-label="Заданная температура воздуха"></div>
        <div class="actions"><button class="action start" data-start disabled>Включить</button><button class="action" data-stop disabled>Выключить</button></div>
        <details class="advanced"><summary>Дополнительные настройки</summary><label data-mode-label for="mode" hidden>Режим печи</label><select data-mode id="mode" hidden></select><button class="stone-settings" data-stone-settings>Температура камней и параметры</button></details>
        <p class="note" data-note></p><p class="error" data-error role="alert" hidden></p></div>
      </ha-card>`;
    this._find('[data-start]').addEventListener('click',()=>{
      if(window.confirm('Включить печь? Убедитесь, что она подготовлена к нагреву и рядом нет посторонних предметов.')) this._service('climate','turn_on');
    });
    this._find('[data-stop]').addEventListener('click',()=>this._service('climate','turn_off'));
    this._find('[data-target]').addEventListener('change',e=>this._service('climate','set_temperature',{temperature:Number(e.target.value)}));
    this._find('[data-mode]').addEventListener('change',e=>this._service('select','select_option',{option:e.target.value},this._config.mode_entity));
    this._find('[data-details]').addEventListener('click',()=>this._moreInfo(this._config.entity));
    this._find('[data-stone-settings]').addEventListener('click',()=>this._moreInfo(this._config.stone_target_entity || this._config.entity));
    this._onVisibility = ()=>this._update();
    this._onMotion = e=>{this._reducedMotion=e.matches;this._update();};
    this._find('video').addEventListener('error',()=>{this._videoFailed=true;this._update();});
  }
  _find(selector){return this.shadowRoot.querySelector(selector);}
  setConfig(config){
    if(!config || !/^climate\.[a-z0-9_]+$/.test(config.entity||'')) throw new Error('Укажите климатическую сущность печи');
    for(const [key,domain] of [['mode_entity','select'],['stone_target_entity','number']]){
      if(config[key] && !new RegExp(`^${domain}\\.[a-z0-9_]+$`).test(config[key])) throw new Error('Некорректная сущность дополнительных настроек');
    }
    if(config.smoke_url){
      const url=new URL(config.smoke_url,window.location.href);
      if(url.origin!==window.location.origin || !url.pathname.startsWith('/local/') || url.username || url.password || url.search || url.hash) throw new Error('Для дыма укажите локальный адрес /local/ без параметров');
    }
    this._config={...config};this._videoFailed=false;
    const video=this._find('video');video.pause();
    if(config.smoke_url)video.src=config.smoke_url;else video.removeAttribute('src');
    this._update();
  }
  set hass(value){this._hass=value;this._update();}
  getCardSize(){return 8;}
  static getStubConfig(){return {entity:'climate.sauna',title:'Сауна'};}
  connectedCallback(){
    document.addEventListener('visibilitychange',this._onVisibility);
    this._motion=matchMedia('(prefers-reduced-motion: reduce)');this._reducedMotion=this._motion.matches;
    this._motion.addEventListener('change',this._onMotion);
    this._observer=new IntersectionObserver(entries=>{this._visible=entries[0]?.isIntersecting??false;this._update();});this._observer.observe(this);this._update();
  }
  disconnectedCallback(){document.removeEventListener('visibilitychange',this._onVisibility);this._motion?.removeEventListener('change',this._onMotion);this._observer?.disconnect();this._find('video').pause();}
  _format(value){return typeof value==='number'&&Number.isFinite(value)?`${value.toLocaleString('ru-RU',{maximumFractionDigits:1})}°`:'—';}
  _update(){
    if(!this._config)return;
    const state=this._hass?.states?.[this._config.entity];const attrs=state?.attributes||{};
    const known=state&&['off','heat'].includes(state.state);const on=known&&state.state==='heat';
    const writable=known&&attrs.control_allowed===true&&!this._pending;
    const status=!state?'Сущность не найдена':state.state==='unavailable'?'Нет связи':!known?'Состояние неизвестно':!on?'Выключена':attrs.hvac_action==='heating'?'Нагревает':'Включена';
    this._find('ha-card').classList.toggle('active',!!on);
    this._find('[data-title]').textContent=this._config.title||'Сауна';
    this._find('[data-status]').textContent=this._pending?'Отправка команды…':status;
    for(const key of ['current','air'])this._find(`[data-${key}]`).textContent=known?this._format(attrs.current_temperature):'—';
    this._find('[data-stone]').textContent=known?this._format(attrs.stone_temperature):'—';
    this._find('[data-setpoint]').textContent=`Заданная: ${known?this._format(attrs.temperature):'—'}`;
    const limits=attrs.limits_known===true&&Number.isFinite(attrs.min_temp)&&Number.isFinite(attrs.max_temp)&&attrs.min_temp<attrs.max_temp;
    const slider=this._find('[data-target]');slider.disabled=!(writable&&on&&limits);
    slider.min=limits?attrs.min_temp:0;slider.max=limits?attrs.max_temp:0;
    if(this.shadowRoot.activeElement!==slider && Number.isFinite(attrs.temperature))slider.value=attrs.temperature;
    this._find('[data-range]').textContent=limits?`${attrs.min_temp}–${attrs.max_temp} °C`:'';
    this._find('[data-start]').disabled=!(writable&&!on&&limits&&Number.isFinite(attrs.current_temperature));
    this._find('[data-stop]').disabled=!writable;
    this._find('[data-note]').textContent=attrs.control_allowed!==true?'Только чтение. Управление разрешается администратором в настройках интеграции.':!on?'Печь не запустится от изменения настроек или открытия карточки.':'Показания обновляются через Home Assistant.';
    const mode=this._hass?.states?.[this._config.mode_entity];const select=this._find('[data-mode]');
    select.hidden=!mode;this._find('[data-mode-label]').hidden=!mode;select.disabled=!(writable&&on);
    const choices=Array.isArray(mode?.attributes?.options)?mode.attributes.options:[];
    if(JSON.stringify(choices)!==this._choices){select.replaceChildren(...choices.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;return option;}));this._choices=JSON.stringify(choices);}
    if(mode)select.value=mode.state;
    this._find('[data-error]').hidden=!this._error;this._find('[data-error]').textContent=this._error;
    const video=this._find('video');const animate=!!(on&&this._config.smoke_url&&this.isConnected&&this._visible&&!document.hidden&&!this._reducedMotion&&!this._videoFailed);
    video.hidden=!animate;
    if(animate&&video.paused){video.muted=true;const promise=video.play();promise?.catch(()=>{this._videoFailed=true;video.hidden=true;});}else if(!animate)video.pause();
  }
  async _service(domain,service,data={},entityId=this._config.entity){
    if(this._pending||!this._hass?.states?.[this._config.entity]?.attributes?.control_allowed)return;
    this._pending=true;this._error='';this._update();
    try{await this._hass.callService(domain,service,{entity_id:entityId,...data});}
    catch(error){this._error=error?.message||'Не удалось выполнить команду. Проверьте состояние печи.';}
    finally{this._pending=false;this._update();}
  }
  _moreInfo(entityId){this.dispatchEvent(new CustomEvent('hass-more-info',{detail:{entityId},bubbles:true,composed:true}));}
}
if(!customElements.get('sangens-card'))customElements.define('sangens-card',SangensCard);
window.customCards=window.customCards||[];
window.customCards.push({type:'sangens-card',name:'Сауна Sangens',description:'Температуры и управление печью с локальным дымом'});
