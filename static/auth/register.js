(function(){
  var $=function(s){return document.querySelector(s)},$$=function(s){return [].slice.call(document.querySelectorAll(s))};
  var panel=$('#panel'),card=$('.form-side');
  requestAnimationFrame(function(){setTimeout(function(){panel.classList.add('in')},150)});
  $$('.eye').forEach(function(b){b.addEventListener('click',function(){var i=document.getElementById(b.dataset.for),on=i.type==='password';i.type=on?'text':'password';b.setAttribute('aria-pressed',on?'true':'false');b.setAttribute('aria-label',on?'Sembunyikan password':'Tampilkan password');i.focus()})});
  var f=$('#f'),go=$('#go'),u=$('#u'),em=$('#e'),p1=$('#p1'),p2=$('#p2'),al=$('#alert'),at=$('#alerttxt');
  function bad(el,on,why){el.setAttribute('aria-invalid',on?'true':'false');if(on)el.setAttribute('aria-describedby','alert');else el.removeAttribute('aria-describedby')}
  function say(t,ok){at.textContent=t;al.className='alert'+(ok?' ok':'');al.hidden=false;delete al.dataset.server}
  function rules(){
    var a=p1.value,b=p2.value;
    var st={len:a.length>=8,num:a.length>0&&!/^\d+$/.test(a),same:a.length>0&&a===b};
    return st;
  }
  [u,em,p1,p2].forEach(function(el){el.addEventListener('input',function(){bad(el,false);if(!al.classList.contains('ok'))al.hidden=true})});
  if(window.matchMedia&&matchMedia('(hover:hover) and (pointer:fine)').matches)setTimeout(function(){u.focus({preventScroll:true})},400);
  f.addEventListener('submit',function(e){
    var st=rules();
    // client-side hints; the real checks (too common, too similar to username, taken username) come from Django
    if(!u.value.trim()){e.preventDefault();bad(u,true);say('Isi username kamu dulu ya.');u.focus();return}
    if(!em.value.trim()||!em.validity.valid){e.preventDefault();bad(em,true);say('Isi email yang benar ya, untuk jaga-jaga kalau kamu lupa password.');em.focus();return}
    if(!st.len||!st.num){e.preventDefault();bad(p1,true);say(!st.len?'Password minimal 8 karakter.':'Password tidak boleh angka semua.');p1.focus();return}
    if(!st.same){e.preventDefault();bad(p2,true);say('Kedua password belum sama.');p2.focus();return}
    f.setAttribute('aria-busy','true');$('#go .t').textContent='Membuat akun...';
    setTimeout(function(){go.disabled=true},0);
  });
  window.addEventListener('pageshow',function(){go.disabled=false;f.removeAttribute('aria-busy');$('#go .t').textContent='Daftar'});
  if(!al.hidden&&al.dataset.server){card.classList.add('shake')}
})();
