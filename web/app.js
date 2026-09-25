const API='http://127.0.0.1:8000';
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const fmt=t=>t?new Date(t).toLocaleString(): '—';
const typeLabel=t=>String(t||'').replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase());
const photoUrl=p=>p?(p.startsWith('http')?p:API+p):'';
async function api(path,opts){const r=await fetch(API+path,opts);if(!r.ok)throw Error(await r.text());return r.json()}
function photoLink(src,type='Detection',id=''){if(!src)return '<span class="muted">No photo</span>';const u=encodeURIComponent(photoUrl(src));return `<a href="photo.html?src=${u}&type=${encodeURIComponent(type)}&id=${id}" title="Open full photo"><img class="thumb" src="${esc(photoUrl(src))}" alt="${esc(type)}"></a>`}
function nav(active){document.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('active',a.dataset.page===active))}
