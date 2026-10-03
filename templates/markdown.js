(function(){
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const inline = (text) => {
    let s = escapeHtml(text);
    const codeSpans = [];
    s = s.replace(/`([^`]+)`/g, (_, value) => {
      const token = `@@YAI_CODE_${codeSpans.length}@@`;
      codeSpans.push(`<code>${value}</code>`);
      return token;
    });
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+)__/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>').replace(/(^|[^_])_([^_]+)_(?!_)/g, '$1<em>$2</em>');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    return s.replace(/@@YAI_CODE_(\d+)@@/g, (_, index) => codeSpans[Number(index)] || '');
  };
  function renderMarkdown(text){
    const normalizedText = String(text || '').replace(/@@YAI_?CODE_?(\d+)@@/g, '[konten tidak tersedia]');
    const lines = normalizedText.replace(/\r\n/g,'\n').split('\n'); let out='', inCode=false, code=[], lang='', list=null, table=false;
    const closeList=()=>{if(list){out+=`</${list}>`;list=null;}};
    const closeTable=()=>{if(table){out+='</tbody></table>';table=false;}};
    for(let i=0;i<lines.length;i++){
      const line=lines[i]; const fence=line.match(/^\s*```\s*([\w-]*)\s*$/);
      if(fence){closeList();closeTable();if(!inCode){inCode=true;lang=fence[1]||'';code=[];}else{out+=`<pre><code class="language-${escapeHtml(lang)}">${escapeHtml(code.join('\n'))}</code></pre>`;inCode=false;}continue;}
      if(inCode){code.push(line);continue;}
      if(!line.trim()){closeList();closeTable();continue;}
      if(/^\s*\|/.test(line) && i+1<lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i+1])){
        closeList(); if(!table){out+='<table><thead><tr>';line.split('|').slice(1,-1).forEach(c=>out+=`<th>${inline(c.trim())}</th>`);out+='</tr></thead><tbody>';table=true;i++;}continue;
      }
      if(table && /^\s*\|/.test(line)){out+='<tr>';line.split('|').slice(1,-1).forEach(c=>out+=`<td>${inline(c.trim())}</td>`);out+='</tr>';continue;} closeTable();
      const h=line.match(/^\s*(#{1,3})\s+(.+)$/); if(h){closeList();out+=`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`;continue;}
      const li=line.match(/^\s*[-*+]\s+(.+)$/); const oi=line.match(/^\s*\d+\.\s+(.+)$/); if(li||oi){const kind=oi?'ol':'ul';if(list!==kind){closeList();out+=`<${kind}>`;list=kind;}out+=`<li>${inline((li||oi)[1])}</li>`;continue;} closeList();
      if(/^\s*>\s?/.test(line)){out+=`<blockquote>${inline(line.replace(/^\s*>\s?/,''))}</blockquote>`;continue;}
      out+=`<p>${inline(line)}</p>`;
    }
    if(inCode) out+=`<pre><code class="language-${escapeHtml(lang)}">${escapeHtml(code.join('\n'))}</code></pre>`;closeList();closeTable();return out;
  }
  window.renderMarkdown = renderMarkdown;
})();
