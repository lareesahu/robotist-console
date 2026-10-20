/* Robotist Content Manager — blog drafts, review and publish.
   Served at /manage/blog/static/blog.js (console pages run under script-src 'self',
   so every handler lives in this file and nothing inline). */
let csrf = '', posts = [], filter = 'draft', busy = false;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function message(text, error = false) {
  const node = $('#message');
  node.textContent = text;
  node.className = error ? 'error' : '';
}

async function api(path, data) {
  const response = await fetch('/manage/blog' + path, data ? {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Catalog-CSRF': csrf},
    body: JSON.stringify(data)
  } : {});
  if (response.status === 401) { window.location.href = '/manage/login?next=/manage/blog/'; throw Error('Please sign in again.'); }
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Request failed.');
  return result;
}

function coverFor(post) {
  const raw = post.coverUrl || ('blog/covers/' + post.slug + '.jpg');
  return raw.startsWith('http') ? raw : '/' + raw.replace(/^\/+/, '');
}

function row(post) {
  const draft = post.status === 'draft';
  const words = String(post.content || '').split(/\s+/).filter(Boolean).length;
  const meta = [post.date, post.category, words ? '~' + words + ' words' : ''].filter(Boolean).join(' · ');
  const acts = draft
    ? `<a class="button" href="/manage/blog/preview/${esc(post.slug)}" target="_blank" rel="noopener">Read draft ↗</a>
       <button data-publish="${esc(post.slug)}">Publish</button>`
    : `<a class="button secondary" href="/blog/${esc(post.slug)}.html" target="_blank" rel="noopener">View live ↗</a>
       <button class="secondary" data-unpublish="${esc(post.slug)}">Unpublish</button>`;
  return `<article class="blog-row">
    <img src="${esc(coverFor(post))}" alt="" loading="lazy">
    <div>
      <span class="badge2 ${draft ? 'draft-b' : 'pub-b'}">${draft ? 'Draft' : 'Published'}</span>
      <h3>${esc(post.title)}</h3>
      <p class="m">${esc(meta)}</p>
      <p class="x">${esc(post.excerpt || '')}</p>
    </div>
    <div class="acts">${acts}</div>
  </article>`;
}

function visible() {
  const term = ($('#blog-search')?.value || '').toLowerCase();
  return posts
    .filter(p => filter === 'all' || (filter === 'draft' ? p.status === 'draft' : p.status !== 'draft'))
    .filter(p => String(p.title || '').toLowerCase().includes(term))
    .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
}

function render() {
  const list = visible();
  $('#posts').innerHTML = list.length
    ? list.map(row).join('')
    : '<p class="note">Nothing here yet. New drafts appear as they are written.</p>';
  document.querySelectorAll('[data-publish]').forEach(b => b.onclick = () => act(b, 'publish', b.dataset.publish));
  document.querySelectorAll('[data-unpublish]').forEach(b => b.onclick = () => act(b, 'unpublish', b.dataset.unpublish));
}

async function act(button, action, slug) {
  if (busy) return;
  const post = posts.find(p => p.slug === slug);
  if (button.dataset.confirmed !== 'yes') {
    button.dataset.confirmed = 'yes';
    button.textContent = action === 'publish' ? 'Confirm publish' : 'Confirm unpublish';
    message(action === 'publish'
      ? 'Click again to publish "' + (post?.title || slug) + '" to the live site.'
      : 'Click again to return "' + (post?.title || slug) + '" to draft. The live page is removed.');
    return;
  }
  busy = true;
  try {
    const result = await api('/api/posts/' + encodeURIComponent(slug) + '/' + action, {});
    posts = posts.map(p => p.slug === slug ? {...p, status: result.status, dateModified: new Date().toISOString().slice(0, 10)} : p);
    counts(result);
    render();
    message(action === 'publish'
      ? 'Published. The article page and sitemap entry appear within about a minute.'
      : 'Returned to draft. The published page is being removed.');
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
  }
}

function counts(extra) {
  const drafts = posts.filter(p => p.status === 'draft').length;
  const published = posts.length - drafts;
  $('#count-draft').textContent = drafts;
  $('#count-published').textContent = published;
}

document.querySelectorAll('[data-filter]').forEach(b => b.onclick = () => {
  filter = b.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  render();
});
$('#blog-search').oninput = render;

(async function start() {
  try {
    const data = await api('/api/posts');
    csrf = data.csrf;
    posts = data.posts || [];
    counts();
    render();
    message(data.github || posts.length === 0 ? '' : '');
  } catch (error) {
    message(error.message, true);
  }
})();
