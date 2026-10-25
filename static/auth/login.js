(function(){
  var $=function(s){return document.querySelector(s)};
  var panel=$('#panel'),card=$('.form-side');
  requestAnimationFrame(function(){setTimeout(function(){panel.classList.add('in')},150)});
  var eye=$('#eye'),pw=$('#p');
  eye.addEventListener('click',function(){var on=pw.type==='password';pw.type=on?'text':'password';eye.setAttribute('aria-pressed',on?'true':'false');eye.setAttribute('aria-label',on?'Sembunyikan password':'Tampilkan password');pw.focus()});
  var caps=$('#caps');
  pw.addEventListener('keyup',function(e){caps.hidden=!(e.getModifierState&&e.getModifierState('CapsLock'))});pw.addEventListener('blur',function(){caps.hidden=true});
  if(window.matchMedia&&matchMedia('(hover:hover) and (pointer:fine)').matches)setTimeout(function(){$('#u').focus({preventScroll:true})},400);
  var f=$('#f'),go=$('#go'),u=$('#u'),al=$('#alert'),at=$('#alerttxt');
  function bad(el,on){el.setAttribute('aria-invalid',on?'true':'false');if(on)el.setAttribute('aria-describedby','alert');else el.removeAttribute('aria-describedby')}
  [u,pw].forEach(function(el){el.addEventListener('input',function(){bad(el,false);if(!al.classList.contains('ok'))al.hidden=true})});
  f.addEventListener('submit',function(e){
    // empty fields -> inline hint; otherwise the form posts to Django and the button shows it is working
    if(!u.value.trim()||!pw.value){e.preventDefault();var miss=!u.value.trim()?u:pw;bad(u,!u.value.trim());bad(pw,!pw.value);at.textContent=!u.value.trim()?'Isi username kamu dulu ya.':'Isi password kamu dulu ya.';al.className='alert';al.hidden=false;miss.focus();return}
    f.setAttribute('aria-busy','true');$('#go .t').textContent='Memeriksa...';
    setTimeout(function(){go.disabled=true},0);
  });
  window.addEventListener('pageshow',function(){go.disabled=false;f.removeAttribute('aria-busy');$('#go .t').textContent='Masuk'});
  if(!al.hidden&&al.dataset.server){bad(u,true);bad(pw,true);card.classList.add('shake');pw.focus()}
})();
