(function(){
  [].slice.call(document.querySelectorAll('.eye')).forEach(function(b){b.addEventListener('click',function(){var i=document.getElementById(b.dataset.for),on=i.type==='password';i.type=on?'text':'password';b.setAttribute('aria-pressed',on?'true':'false');b.setAttribute('aria-label',on?'Sembunyikan password':'Tampilkan password');i.focus()})});
  var panel=document.getElementById('panel');
  if(panel)requestAnimationFrame(function(){setTimeout(function(){panel.classList.add('in')},150)});
})();
