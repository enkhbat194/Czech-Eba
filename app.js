(() => {
  const root = document.getElementById('root');
  const profiles = [
    { id: 'eba', name: 'Эба', sub: 'Эбагийн хичээл', color: '#2ccbe8' },
    { id: 'unuruu', name: 'Өнөрөө', sub: 'Өнөрөөгийн хичээл', color: '#ff7a16' }
  ];
  const baseLessons = [
    { text: 'Ahoj, jak se máš?', mn: 'Сайн уу, сонин сайхан юу байна?', pron: 'Ахой, як сэ мааш?', tip: '2-р хичээл дээр үзсэн мэндчилгээний бүтцийг ашиглана уу.' },
    { text: 'Jmenuji se {name}.', mn: 'Намайг {name} гэдэг.', pron: 'Йменуйи сэ {name}.', tip: 'Jmenuji se = Намайг ... гэдэг гэсэн утгатай.' },
    { text: 'Děkuji, mám se dobře.', mn: 'Баярлалаа, би сайн байна.', pron: 'Декуйи, маам сэ добрже.', tip: 'mám se dobře = би сайн байна.' }
  ];
  let selectedProfile = profiles.find(p => p.id === localStorage.getItem('octo_profile')) || null;
  const state = { screen: selectedProfile ? (localStorage.getItem('octo_screen') || 'lesson') : 'profiles', lessonIndex:0, correctWordIndices:[], isLessonCompleted:false, listening:false, error:'' };
  const save = () => localStorage.setItem('octo_screen', state.screen);
  const lesson = () => {
    const source = baseLessons[state.lessonIndex];
    const name = selectedProfile ? selectedProfile.name : 'Эба';
    return {
      ...source,
      text: source.text.replaceAll('{name}', name),
      mn: source.mn.replaceAll('{name}', name),
      pron: source.pron.replaceAll('{name}', name)
    };
  };
  const cleanWords = (text) => text.toLocaleLowerCase('cs-CZ').replace(/[^\p{L}\p{N}\s]/gu, '').trim().split(/\s+/).filter(Boolean);
  const targetWords = () => cleanWords(lesson().text);
  const speech = () => window.SpeechRecognition || window.webkitSpeechRecognition;
  function header(progress){ return `<div class="top"><button class="close" id="close">×</button><div class="prog"><div class="progline"><i style="width:${Math.max(12,(progress/9)*100)}%"></i></div></div><span class="progressText">${progress}/9</span></div>`; }
  function profileScreen(){
    root.innerHTML = `<section class="profileScreen"><img class="profileMark" src="./assets/octolearn-mark.svg" alt="OctoLearn"/><p class="eyebrow">ХУВИЙН СУРГАЛТ</p><h1 class="homeTitle">Хэн сурах вэ?</h1><p class="sub">Суралцагчаа сонго. Ахиц тус тусдаа хадгалагдана.</p><div class="profileCards">${profiles.map(p => `<button class="profileCard" data-profile="${p.id}" style="--profile:${p.color}"><span class="profileAvatar">${p.name.slice(0,1)}</span><span><b>${p.name}</b><small>${p.sub}</small></span><i>›</i></button>`).join('')}</div></section>`;
    document.querySelectorAll('[data-profile]').forEach(button => button.onclick = () => {
      selectedProfile = profiles.find(p => p.id === button.dataset.profile);
      localStorage.setItem('octo_profile', selectedProfile.id);
      state.screen = 'lesson'; save(); state.lessonIndex = 0; state.correctWordIndices=[]; state.error=''; renderLesson();
    });
  }
  function levels(){
    const list=[['A0','Суурь','Өдөр тутмын үг хэллэг','var(--cyan)'],['A1','Анхан','Маш энгийн үг хэллэг мэднэ','#77d78c'],['A2','Анхан дунд','Энгийн харилцаа хийж чадна','#ffb348'],['B1','Дунд','Ихэнх нөхцөлд ойлголцоно','var(--orange)'],['B2','Дундаас дээш','Мэргэжлийн хэлэлцүүлэг хийнэ','#bd70ff'],['C1','Ахисан түвшин','Уян хатан, үр дүнтэй ашиглана','#ff5bb2'],['C2','Мэргэжлийн','Төрөлх хэлтэй адил','#ead800']];
    root.innerHTML=`<section><div class="brand"><img src="./assets/octolearn-mark.svg" alt="OctoLearn"/> <span>Чех хэл</span></div><div class="homeTitle">Түвшинээ сонгоорой</div><p class="sub">Чех хэлний мэдлэгийнхээ түвшинтэй тохирохыг сонгоно уу.</p>${list.map(([code,title,desc,color])=>`<div class="level ${code==='A0'?'active':''}"><div class="badge" style="color:${color}">${code}</div><div><b>${title}</b><small>${desc}</small></div><button aria-label="${code}"></button></div>`).join('')}<button class="primary" id="start">Сургалтаа эхлүүлэх</button></section>`;
    document.getElementById('start').onclick=()=>{state.screen='profiles';save();profileScreen();};
  }
  function replay(){ if(!('speechSynthesis' in window)) return; window.speechSynthesis.cancel(); const utterance=new SpeechSynthesisUtterance(lesson().text); utterance.lang='cs-CZ'; utterance.rate=.82; window.speechSynthesis.speak(utterance); }
  function checkCompletion(){ const targets=targetWords(); if(state.correctWordIndices.length!==targets.length || state.isLessonCompleted) return; state.isLessonCompleted=true; renderLesson(); window.setTimeout(()=>{state.lessonIndex=(state.lessonIndex+1)%baseLessons.length;state.correctWordIndices=[];state.isLessonCompleted=false;state.listening=false;state.error='';renderLesson();},1500); }
  function startRecognition(){
    if(state.isLessonCompleted) return; const Recognition=speech();
    if(!Recognition){state.error='Энэ browser дуудлага таних функцийг дэмжихгүй байна.';renderLesson();return;}
    state.error='';state.listening=true;state.correctWordIndices=[];renderLesson();
    const recognition=new Recognition();recognition.lang='cs-CZ';recognition.continuous=false;recognition.interimResults=true;recognition.maxAlternatives=1;
    recognition.onresult=(event)=>{let transcript='';for(let i=event.resultIndex;i<event.results.length;i++)transcript+=' '+event.results[i][0].transcript;const spoken=cleanWords(transcript);const targets=targetWords();const found=new Set(state.correctWordIndices);spoken.forEach(word=>{const index=targets.findIndex((target,i)=>target===word&&!found.has(i));if(index!==-1)found.add(index);});state.correctWordIndices=[...found].sort((a,b)=>a-b);renderLesson();checkCompletion();};
    recognition.onerror=(event)=>{state.listening=false;state.error=event.error==='not-allowed'?'Микрофоны зөвшөөрөл өгөөгүй байна.':'Дуу танигдсангүй. Дахин удаан хэлж үзээрэй.';renderLesson();};
    recognition.onend=()=>{if(!state.isLessonCompleted){state.listening=false;renderLesson();}};recognition.start();
  }
  function renderLesson(){
    const current=lesson(); const buttonClass=state.isLessonCompleted?'primary success':state.listening?'primary listening':'primary'; const buttonText=state.isLessonCompleted?'✓ Үргэлжлүүлэх':state.listening?'🎙 Сонсож байна...':'🎤 Дуудлага шалгах'; const display=current.text.replace(/^([^ ]+)/,'<span class="hit">$1</span>');
    root.innerHTML=`${header(state.lessonIndex+1)}<section class="learnerBar"><span>${selectedProfile ? selectedProfile.name : ''}</span><button id="changeProfile">Солих</button></section><section class="octoTip"><img class="octoLogo" src="./assets/octolearn-mark.svg" alt="OctoLearn багш"/><div class="tip">${current.tip}</div></section><section class="phrase"><h1>${display}</h1><p class="pronGuide">Дуудлага: ${current.pron}</p><p class="translation">${current.mn}</p><button class="replay" id="replay">🔊</button><div class="replayLabel">Дахин сонсох</div></section><div class="actions"><div class="secondary"><button id="flash">🗂 Флэшкарт+</button><button id="skip">⏭ Алгасах</button></div>${state.error?`<p class="notice">${state.error}</p>`:''}<button class="${buttonClass}" id="speak">${buttonText}</button></div>`;
    document.getElementById('replay').onclick=replay;document.getElementById('speak').onclick=startRecognition;document.getElementById('skip').onclick=()=>{state.lessonIndex=(state.lessonIndex+1)%baseLessons.length;state.correctWordIndices=[];state.error='';renderLesson();};document.getElementById('flash').onclick=()=>alert(`${current.text}\nДуудлага: ${current.pron}\n${current.mn}`);document.getElementById('close').onclick=()=>{state.screen='profiles';save();profileScreen();};document.getElementById('changeProfile').onclick=()=>{state.screen='profiles';save();profileScreen();};
  }
  function boot(){ if(!selectedProfile) profileScreen(); else if(state.screen==='levels') levels(); else if(state.screen==='profiles') profileScreen(); else renderLesson(); }
  boot();
})();