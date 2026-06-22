(() => {
  const root = document.getElementById('root');
  const lessons = [
    { text: 'Ahoj, jak se máš?', mn: 'Сайн уу, сонин сайхан юу байна?', tip: "2-р хичээл дээр үзсэн мэндчилгээний бүтцийг ашиглана уу." },
    { text: 'Jmenuji se Bat.', mn: 'Намайг Бат гэдэг.', tip: "Jmenuji se = Намайг ... гэдэг гэсэн утгатай." },
    { text: 'Děkuji, mám se dobře.', mn: 'Баярлалаа, би сайн байна.', tip: "mám se dobře = би сайн байна." }
  ];
  const state = { screen: localStorage.getItem('octo_screen') || 'levels', level:'A0', lessonIndex:0, correctWordIndices:[], isLessonCompleted:false, listening:false, error:'' };
  const save = () => localStorage.setItem('octo_screen', state.screen);
  const cleanWords = (text) => text.toLocaleLowerCase('cs-CZ').replace(/[^\p{L}\p{N}\s]/gu, '').trim().split(/\s+/).filter(Boolean);
  const targetWords = () => cleanWords(lessons[state.lessonIndex].text);
  const speech = () => window.SpeechRecognition || window.webkitSpeechRecognition;

  function header(progress){ return `<div class="top"><button class="close" id="close">×</button><div class="prog"><div class="progline"><i style="width:${Math.max(12,(progress/9)*100)}%"></i></div></div><span class="progressText">${progress}/9</span></div>`; }

  function levels(){
    const list=[['A0','Суурь','Өдөр тутмын үг хэллэг','var(--cyan)'],['A1','Анхан','Маш энгийн үг хэллэг мэднэ','#77d78c'],['A2','Анхан дунд','Энгийн харилцаа хийж чадна','#ffb348'],['B1','Дунд','Ихэнх нөхцөлд ойлголцоно','var(--orange)'],['B2','Дундаас дээш','Мэргэжлийн хэлэлцүүлэг хийнэ','#bd70ff'],['C1','Ахисан түвшин','Уян хатан, үр дүнтэй ашиглана','#ff5bb2'],['C2','Мэргэжлийн','Төрөлх хэлтэй адил','#ead800']];
    root.innerHTML=`<section><div class="homeTitle">Түвшинээ сонгоорой</div><p class="sub">Чех хэлний мэдлэгийнхээ түвшинтэй тохирохыг сонгоно уу.</p>${list.map(([code,title,desc,color])=>`<div class="level ${state.level===code?'active':''}" data-level="${code}"><div class="badge" style="color:${color}">${code}</div><div><b>${title}</b><small>${desc}</small></div><button aria-label="${code}"></button></div>`).join('')}<button class="primary" id="start">${state.level} · Суурь түвшнээс эхлэх</button></section>`;
    document.querySelectorAll('[data-level]').forEach(el=>el.onclick=()=>{state.level=el.dataset.level; levels();});
    document.getElementById('start').onclick=()=>{state.screen='birthday';save();birthday();};
  }

  function birthday(){
    root.innerHTML=`<section class="birthday"><div class="cake">🎂</div><h1 class="homeTitle">Төрсөн өдрөө оруулна уу</h1><p class="sub">Бид таны суралцах туршлагыг хувийн болгоход ашиглана</p><div class="wheel"><div><span>1988</span><span>1989</span><strong>1990</strong><span>1991</span><span>1992</span></div><div><span>March</span><span>April</span><strong>May</strong><span>June</span><span>July</span></div><div><span>1</span><span>2</span><strong>3</strong><span>4</span><span>5</span></div></div><div class="selectedDate">1990 оны 05 сарын 03</div><button class="primary orange" id="continue">Үргэлжлүүлэх</button></section>`;
    document.getElementById('continue').onclick=()=>{state.screen='lesson';save();renderLesson();};
  }

  function replay(){
    if(!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(lessons[state.lessonIndex].text);u.lang='cs-CZ';u.rate=.82;window.speechSynthesis.speak(u);
  }

  function checkCompletion(){
    const targets=targetWords();
    if(state.correctWordIndices.length!==targets.length || state.isLessonCompleted) return;
    state.isLessonCompleted=true; renderLesson();
    window.setTimeout(()=>{
      state.lessonIndex=(state.lessonIndex+1)%lessons.length;
      state.correctWordIndices=[];
      state.isLessonCompleted=false;
      state.listening=false;
      state.error='';
      renderLesson();
    },1500);
  }

  function startRecognition(){
    if(state.isLessonCompleted) return;
    const Recognition=speech();
    if(!Recognition){ state.error='Энэ browser microphone speech recognition дэмжихгүй байна.'; renderLesson(); return; }
    state.error=''; state.listening=true; state.correctWordIndices=[]; renderLesson();
    const recognition=new Recognition(); recognition.lang='cs-CZ'; recognition.continuous=false; recognition.interimResults=true; recognition.maxAlternatives=1;
    recognition.onresult=(event)=>{
      let transcript=''; for(let i=event.resultIndex;i<event.results.length;i++) transcript += ' '+event.results[i][0].transcript;
      const spoken=cleanWords(transcript); const targets=targetWords(); const found=new Set(state.correctWordIndices);
      spoken.forEach(word=>{ const index=targets.findIndex((target,i)=>target===word&&!found.has(i)); if(index!==-1) found.add(index); });
      state.correctWordIndices=[...found].sort((a,b)=>a-b); renderLesson(); checkCompletion();
    };
    recognition.onerror=(event)=>{ state.listening=false; state.error=event.error==='not-allowed'?'Микрофоны зөвшөөрөл өгөөгүй байна.':'Дуу танигдсангүй. Дахин удаан хэлж үзээрэй.'; renderLesson(); };
    recognition.onend=()=>{ if(!state.isLessonCompleted){state.listening=false;renderLesson();} };
    recognition.start();
  }

  function renderLesson(){
    const lesson=lessons[state.lessonIndex]; const words=targetWords(); const completed=state.correctWordIndices.length;
    const buttonClass=state.isLessonCompleted?'primary success':state.listening?'primary listening':'primary';
    const buttonText=state.isLessonCompleted?'✓ Үргэлжлүүлэх':state.listening?'🎙 Сонсож байна...':'🎤 Дуудлага шалгах';
    const display=lesson.text.replace(/^([^ ]+)/, '<span class="hit">$1</span>');
    root.innerHTML=`${header(state.lessonIndex+1)}<section class="octoTip"><div class="octo">🐙</div><div class="tip">${lesson.tip}</div></section><section class="phrase"><h1>${display}</h1><p class="translation">${lesson.mn}</p><button class="replay" id="replay">🔊</button><div class="replayLabel">Replay</div></section><div class="actions"><div class="secondary"><button id="flash">🗂 Флэшкарт+</button><button id="skip">⏭ Алгасах</button></div>${state.error?`<p class="notice">${state.error}</p>`:''}<button class="${buttonClass}" id="speak">${buttonText}</button></div>`;
    document.getElementById('replay').onclick=replay;
    document.getElementById('speak').onclick=startRecognition;
    document.getElementById('skip').onclick=()=>{state.lessonIndex=(state.lessonIndex+1)%lessons.length;state.correctWordIndices=[];renderLesson();};
    document.getElementById('flash').onclick=()=>alert(`${lesson.text}\n${lesson.mn}`);
    document.getElementById('close').onclick=()=>{state.screen='levels';save();levels();};
  }

  function boot(){ if(state.screen==='birthday') birthday(); else if(state.screen==='lesson') renderLesson(); else levels(); }
  boot();
})();