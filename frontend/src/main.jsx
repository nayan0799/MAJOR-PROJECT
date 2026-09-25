import React, {useEffect, useMemo, useState} from "react";
import {createRoot} from "react-dom/client";
import {MapContainer, TileLayer, Marker, Popup} from "react-leaflet";
import {Phone, Moon, Sun, Globe, LayoutDashboard, AlertTriangle, Trash2, Map, BarChart3, Camera, Settings, Menu, X, CheckCircle2} from "lucide-react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "./styles.css";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:"https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl:"https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:"https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"
});

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const T = {
  en:{dashboard:"Dashboard",incidents:"Incidents",map:"Live Map",garbage:"Garbage Photos",analytics:"Analytics",settings:"Settings",total:"Total Reports",pothole:"Potholes",garbageN:"Garbage",road:"Road Damage",person:"Person",call:"Call Bus Driver",recent:"Recent Incidents",upload:"Upload Garbage Photo",language:"Language",theme:"Theme",dark:"Dark",light:"Light",status:"Status",type:"Type",confidence:"Confidence",action:"Action",resolve:"Resolve",delete:"Delete",choose:"Choose image",save:"Upload",noData:"No incidents found"},
  hi:{dashboard:"डैशबोर्ड",incidents:"घटनाएँ",map:"लाइव मैप",garbage:"कचरा फोटो",analytics:"विश्लेषण",settings:"सेटिंग्स",total:"कुल रिपोर्ट",pothole:"गड्ढे",garbageN:"कचरा",road:"सड़क क्षति",person:"व्यक्ति",call:"बस ड्राइवर को कॉल",recent:"हाल की घटनाएँ",upload:"कचरा फोटो अपलोड",language:"भाषा",theme:"थीम",dark:"डार्क",light:"लाइट",status:"स्थिति",type:"प्रकार",confidence:"विश्वास",action:"कार्य",resolve:"हल करें",delete:"हटाएँ",choose:"फोटो चुनें",save:"अपलोड",noData:"कोई घटना नहीं मिली"},
  mni:{dashboard:"Dashboard",incidents:"Incidents",map:"Live Map",garbage:"Garbage Photos",analytics:"Analytics",settings:"Settings",total:"Total Reports",pothole:"Potholes",garbageN:"Garbage",road:"Road Damage",person:"Person",call:"Bus Driver-da Call",recent:"Recent Incidents",upload:"Garbage Photo Upload",language:"Language",theme:"Theme",dark:"Dark",light:"Light",status:"Status",type:"Type",confidence:"Confidence",action:"Action",resolve:"Resolve",delete:"Delete",choose:"Choose image",save:"Upload",noData:"Incident amadi leitre"}
};

function App(){
  const [page,setPage]=useState("dashboard"), [dark,setDark]=useState(localStorage.theme==="dark");
  const [lang,setLang]=useState(localStorage.lang||"en"), [open,setOpen]=useState(false);
  const [incidents,setIncidents]=useState([]), [driver,setDriver]=useState("");
  const t=T[lang];

  const load=async()=>{try{const r=await fetch(API+"/incidents"); if(r.ok)setIncidents(await r.json())}catch(e){console.error(e)}};
  useEffect(()=>{load(); fetch(API+"/settings").then(r=>r.json()).then(x=>setDriver(x.bus_driver_phone||"")).catch(()=>{}); const i=setInterval(load,5000); return()=>clearInterval(i)},[]);
  useEffect(()=>{document.body.className=dark?"dark":""; localStorage.theme=dark?"dark":"light"},[dark]);
  useEffect(()=>{localStorage.lang=lang},[lang]);

  const counts=useMemo(()=>({
    total:incidents.length,
    pothole:incidents.filter(x=>x.type==="pothole").length,
    garbage:incidents.filter(x=>x.type==="garbage").length,
    road:incidents.filter(x=>x.type==="road_damage").length,
    person:incidents.filter(x=>x.type==="person").length
  }),[incidents]);

  async function updateStatus(id,status){
    await fetch(`${API}/incidents/${id}/status`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})}); load();
  }
  async function remove(id){
    if(confirm("Delete this incident?")){await fetch(`${API}/incidents/${id}`,{method:"DELETE"});load();}
  }

  const nav=[
    ["dashboard",LayoutDashboard,t.dashboard],["incidents",AlertTriangle,t.incidents],["map",Map,t.map],
    ["garbage",Camera,t.garbage],["analytics",BarChart3,t.analytics],["settings",Settings,t.settings]
  ];

  return <div className="app">
    <aside className={open?"side open":"side"}>
      <div className="brand">🚌 <span>AI Smart Bus</span><button className="close" onClick={()=>setOpen(false)}><X/></button></div>
      <nav>{nav.map(([id,Icon,label])=><button className={page===id?"active":""} onClick={()=>{setPage(id);setOpen(false)}} key={id}><Icon size={19}/>{label}</button>)}</nav>
      <div className="driverBox">
        <b>{t.call}</b>
        <a href={driver?`tel:${driver}`:"#"} className="callBtn" onClick={e=>{if(!driver){e.preventDefault();alert("Set BUS_DRIVER_PHONE in backend .env")}}}><Phone size={18}/>{driver||"+91 Driver"}</a>
      </div>
    </aside>

    <main>
      <header><button className="menu" onClick={()=>setOpen(true)}><Menu/></button><h1>{nav.find(x=>x[0]===page)?.[2]}</h1><div className="tools">
        <select value={lang} onChange={e=>setLang(e.target.value)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="mni">Meiteilon</option></select>
        <button onClick={()=>setDark(!dark)} title={dark?t.light:t.dark}>{dark?<Sun/>:<Moon/>}</button>
      </div></header>

      {page==="dashboard" && <Dashboard counts={counts} incidents={incidents} t={t} updateStatus={updateStatus} remove={remove}/>}
      {page==="incidents" && <IncidentPage incidents={incidents} t={t} updateStatus={updateStatus} remove={remove}/>}
      {page==="map" && <MapPage incidents={incidents}/>}
      {page==="garbage" && <GarbagePage t={t} reload={load}/>}
      {page==="analytics" && <Analytics counts={counts} incidents={incidents}/>}
      {page==="settings" && <SettingsPage t={t} driver={driver}/>}
    </main>
  </div>
}

function Dashboard({counts,incidents,t,updateStatus,remove}){
 return <section className="content">
  <div className="cards">{[[t.total,counts.total,""],[t.pothole,counts.pothole,"pothole"],[t.garbageN,counts.garbage,"garbage"],[t.road,counts.road,"road"],[t.person,counts.person,"person"]].map(x=><div className="card" key={x[0]}><small>{x[0]}</small><strong>{x[1]}</strong></div>)}</div>
  <div className="panel"><div className="panelTitle"><h2>{t.recent}</h2><span>{incidents.length}</span></div><IncidentTable incidents={incidents.slice(0,10)} t={t} updateStatus={updateStatus} remove={remove}/></div>
 </section>
}

function IncidentPage({incidents,t,updateStatus,remove}){
 const [filter,setFilter]=useState("all");
 const rows=filter==="all"?incidents:incidents.filter(x=>x.type===filter);
 return <section className="content"><div className="toolbar"><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All</option><option value="pothole">{t.pothole}</option><option value="garbage">{t.garbageN}</option><option value="road_damage">{t.road}</option><option value="person">{t.person}</option></select></div><div className="panel"><IncidentTable incidents={rows} t={t} updateStatus={updateStatus} remove={remove}/></div></section>
}

function IncidentTable({incidents,t,updateStatus,remove}){
 if(!incidents.length)return <div className="empty">{t.noData}</div>;
 return <div className="tableWrap"><table><thead><tr><th>{t.type}</th><th>{t.confidence}</th><th>{t.status}</th><th>Time</th><th>{t.action}</th></tr></thead><tbody>{incidents.map(i=><tr key={i.id}>
  <td><b>{i.type}</b>{i.photo&&<img className="thumb" src={i.photo} />}</td>
  <td>{Math.round((i.confidence||0)*100)}%</td><td><span className={"status "+i.status}>{i.status}</span></td>
  <td>{i.created_at?new Date(i.created_at).toLocaleString():"-"}</td>
  <td className="actions"><button onClick={()=>updateStatus(i.id,"resolved")}><CheckCircle2 size={16}/>{t.resolve}</button><button className="danger" onClick={()=>remove(i.id)}><Trash2 size={16}/>{t.delete}</button></td>
 </tr>)}</tbody></table></div>
}

function MapPage({incidents}){
 const center=[23.83,91.28]; return <section className="content"><div className="panel mapPanel"><MapContainer center={center} zoom={12} style={{height:"68vh",width:"100%"}}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>{incidents.filter(i=>i.latitude&&i.longitude).map(i=><Marker key={i.id} position={[i.latitude,i.longitude]}><Popup><b>{i.type}</b><br/>Confidence: {Math.round((i.confidence||0)*100)}%<br/>{i.status}</Popup></Marker>)}</MapContainer></div></section>
}

function GarbagePage({t,reload}){
 const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[msg,setMsg]=useState("");
 async function upload(e){e.preventDefault(); if(!file)return; setBusy(true);setMsg("");const fd=new FormData();fd.append("file",file);fd.append("confidence","1");fd.append("description","Manual garbage report");try{const r=await fetch(API+"/incidents/upload-garbage",{method:"POST",body:fd});const x=await r.json();if(!r.ok)throw Error(x.detail||"Upload failed");setMsg("Uploaded successfully.");setFile(null);e.target.reset();reload()}catch(err){setMsg(err.message)}finally{setBusy(false)}}
 return <section className="content"><div className="panel uploadPanel"><h2>{t.upload}</h2><p>Photos are stored in Supabase Storage and the incident record is saved in Supabase Database.</p><form onSubmit={upload}><label className="drop"><Camera size={40}/><span>{file?file.name:t.choose}</span><input type="file" accept="image/*" capture="environment" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><button className="primary" disabled={!file||busy}>{busy?"Uploading...":t.save}</button></form>{msg&&<p className="message">{msg}</p>}</div></section>
}

function Analytics({counts,incidents}){
 const max=Math.max(1,counts.pothole,counts.garbage,counts.road,counts.person);
 return <section className="content"><div className="panel"><h2>Detection Analytics</h2>{[["Potholes",counts.pothole],["Garbage",counts.garbage],["Road Damage",counts.road],["Person",counts.person]].map(([n,v])=><div className="barRow" key={n}><span>{n}</span><div><i style={{width:`${v/max*100}%`}}></i></div><b>{v}</b></div>)}<p>Total records: {incidents.length}</p></div></section>
}

function SettingsPage({t,driver}){
 return <section className="content"><div className="panel settings"><h2>{t.settings}</h2><div><label>{t.language}</label><p>Use the language selector in the top-right corner.</p></div><div><label>{t.theme}</label><p>Use the sun/moon button to switch between light and dark mode.</p></div><div><label>Driver phone</label><p>{driver||"Not configured"}</p></div></div></section>
}

createRoot(document.getElementById("root")).render(<App/>);
