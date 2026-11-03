/* Robotist Content Manager — blog list, editor, bulk actions.
   Served at /manage/blog/static/blog.js (console pages run under script-src 'self',
   so every handler lives in this file and nothing inline). */
let csrf = '', posts = [], filter = 'draft', busy = false, editing = null;
const selected = new Set();
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const words = html => String(html || '').replace(/<[^>]*>/g, ' ').split(/\s+/).filter(Boolean).length;

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
  const count = words(post.content);
  const meta = [post.date, post.category, count ? count + ' words' : ''].filter(Boolean).join(' · ');
  const tags = (post.keywords || []).slice(0, 3).map(k => '<span>' + esc(k) + '</span>').join('');
  const acts = draft
    ? '<a class="button" href="/manage/blog/preview/' + esc(post.slug) + '" target="_blank" rel="noopener">Read draft ↗</a>' +
      '<button class="secondary" data-edit="' + esc(post.slug) + '">Edit</button>' +
      '<button data-publish="' + esc(post.slug) + '">Publish</button>'
    : '<a class="button secondary" href="/blog/' + esc(post.slug) + '.html" target="_blank" rel="noopener">View live ↗</a>' +
      '<button class="secondary" data-edit="' + esc(post.slug) + '">Edit</button>' +
      '<button class="secondary" data-unpublish="' + esc(post.slug) + '">Unpublish</button>';
  return '<article class="blog-row' + (selected.has(post.slug) ? ' sel' : '') + '" data-row="' + esc(post.slug) + '">' +
    '<input class="pick" type="checkbox" data-pick="' + esc(post.slug) + '" aria-label="Select ' + esc(post.title) + '"' + (selected.has(post.slug) ? ' checked' : '') + '>' +
    '<img src="' + esc(coverFor(post)) + '" alt="" loading="lazy">' +
    '<div><span class="badge2 ' + (draft ? 'draft-b' : 'pub-b') + '">' + (draft ? 'Draft' : 'Published') + '</span>' +
    '<h3>' + esc(post.title) + '</h3><p class="m">' + esc(meta) + '</p>' +
    '<p class="x">' + esc(post.excerpt || '') + '</p><div class="tags">' + tags + '</div></div>' +
    '<div class="acts">' + acts + '</div></article>';
}

function visible() {
  const term = ($('#blog-search')?.value || '').toLowerCase();
  return posts
    .filter(p => filter === 'all' || (filter === 'draft' ? p.status === 'draft' : p.status !== 'draft'))
    .filter(p => !term || [p.title, p.slug, p.category, (p.keywords || []).join(' ')]
      .some(v => String(v || '').toLowerCase().includes(term)))
    .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
}

function render() {
  const list = visible();
  $('#posts').innerHTML = list.length
    ? list.map(row).join('')
    : '<p class="note">Nothing here. Drafts appear as they are written, or start one with New article.</p>';
  document.querySelectorAll('[data-publish]').forEach(b => b.onclick = () => act(b, 'publish', b.dataset.publish));
  document.querySelectorAll('[data-unpublish]').forEach(b => b.onclick = () => act(b, 'unpublish', b.dataset.unpublish));
  document.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => openEditor(b.dataset.edit));
  document.querySelectorAll('[data-pick]').forEach(box => box.onchange = () => {
    box.checked ? selected.add(box.dataset.pick) : selected.delete(box.dataset.pick);
    box.closest('.blog-row').classList.toggle('sel', box.checked);
    paintSelection();
  });
  const all = $('#select-all');
  all.checked = list.length > 0 && list.every(p => selected.has(p.slug));
  all.indeterminate = !all.checked && list.some(p => selected.has(p.slug));
  paintSelection();
}

function paintSelection() {
  const count = selected.size;
  $('#bulk-bar').classList.toggle('on', count > 0);
  $('#sel-count').textContent = count;
  document.querySelectorAll('[data-bulk]').forEach(b => {
    if (b.dataset.bulk === 'clear') return;
    if (b.dataset.confirmed === 'yes') { b.dataset.confirmed = ''; b.textContent = b.dataset.bulk.charAt(0).toUpperCase() + b.dataset.bulk.slice(1); }
  });
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
    posts = posts.map(p => p.slug === slug ? Object.assign({}, p, {status: result.status, dateModified: new Date().toISOString().slice(0, 10)}) : p);
    counts();
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

function counts() {
  const drafts = posts.filter(p => p.status === 'draft').length;
  $('#count-draft').textContent = drafts;
  $('#count-published').textContent = posts.length - drafts;
  $('#count-all').textContent = posts.length;
}

/* Editor */
function faqRow(q, a) {
  const row = document.createElement('div');
  row.className = 'ed-faq-row';
  row.innerHTML = '<input class="faq-q" placeholder="Question" value="' + esc(q || '') + '">' +
    '<input class="faq-a" placeholder="Answer" value="' + esc(a || '') + '">' +
    '<button type="button" class="secondary" aria-label="Remove question">✕</button>';
  row.querySelector('button').onclick = () => row.remove();
  return row;
}

function slugify(text) {
  return String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70);
}

function openEditor(slug) {
  const post = slug ? posts.find(p => p.slug === slug) : null;
  editing = post ? post.slug : null;
  $('#editor-heading').textContent = post ? 'Edit article' : 'New article';
  $('#f-title').value = post?.title || '';
  $('#f-slug').value = post?.slug || '';
  $('#f-slug').dataset.touched = post ? 'yes' : '';
  $('#f-category').value = post?.category || 'Deployment';
  $('#f-date').value = post?.date || new Date().toLocaleDateString('en-US', {month: 'long', day: '2-digit', year: 'numeric'});
  $('#f-read').value = post?.readTime || '';
  $('#f-excerpt').value = post?.excerpt || '';
  $('#f-cover').value = post?.coverUrl || '';
  $('#f-seo').value = post?.seoTitle || '';
  $('#f-meta').value = post?.metaDescription || '';
  $('#f-keywords').value = (post?.keywords || []).join(', ');
  $('#f-status').value = post?.status === 'published' ? 'published' : 'draft';
  $('#f-content').value = post?.content || '';
  $('#f-faq').innerHTML = '';
  (post?.faq || []).forEach(f => $('#f-faq').appendChild(faqRow(f.q, f.a)));
  $('#ed-delete').style.display = post ? '' : 'none';
  $('#ed-delete').dataset.confirmed = '';
  $('#ed-delete').textContent = 'Delete article';
  $('#ed-preview').disabled = !post;
  $('#f-cover-preview').src = post?.coverUrl ? coverFor(post) : '';
  $('#blog-editor').classList.add('on');
  $('#blog-editor').scrollIntoView({behavior: 'smooth', block: 'start'});
  countsUpdate();
  $('#f-title').focus();
}

function closeEditor() {
  $('#blog-editor').classList.remove('on');
  editing = null;
}

function collect() {
  const faq = [...$('#f-faq').children].map(r => ({
    q: r.querySelector('.faq-q').value.trim(),
    a: r.querySelector('.faq-a').value.trim()
  })).filter(f => f.q && f.a);
  const slug = $('#f-slug').value.trim() || slugify($('#f-title').value);
  return {
    title: $('#f-title').value.trim(),
    slug: slug,
    category: $('#f-category').value.trim(),
    date: $('#f-date').value.trim(),
    readTime: $('#f-read').value.trim() || (Math.max(3, Math.ceil(words($('#f-content').value) / 200)) + ' min'),
    excerpt: $('#f-excerpt').value.trim(),
    coverUrl: $('#f-cover').value.trim() || ('blog/covers/' + slug + '.jpg'),
    seoTitle: $('#f-seo').value.trim(),
    metaDescription: $('#f-meta').value.trim(),
    keywords: $('#f-keywords').value.split(',').map(s => s.trim()).filter(Boolean),
    status: $('#f-status').value,
    faq: faq,
    content: $('#f-content').value
  };
}

function countsUpdate() {
  const title = $('#f-title').value.length;
  const seo = $('#f-seo').value.length;
  const meta = $('#f-meta').value.length;
  $('#f-title-count').textContent = title ? title + ' chars' : '';
  $('#f-seo-count').textContent = seo ? seo + '/60' : '';
  $('#f-meta-count').textContent = meta ? meta + '/158' : '';
  $('#f-word-count').textContent = words($('#f-content').value) + ' words';
  $('#f-seo-count').style.color = seo > 60 ? '#ffb4b4' : '';
  $('#f-meta-count').style.color = meta > 158 ? '#ffb4b4' : '';
}

async function save() {
  if (busy) return;
  const post = collect();
  busy = true;
  $('#ed-save').disabled = true;
  try {
    const result = await api('/api/posts/save', {originalSlug: editing, post: post});
    posts = editing
      ? posts.map(p => p.slug === editing ? result.post : p)
      : [result.post].concat(posts);
    editing = result.post.slug;
    counts();
    render();
    message('Saved "' + result.post.title + '". ' + (result.post.status === 'published'
      ? 'It is live and the article page rebuilds within a minute.'
      : 'It stays a draft until you publish it.'));
    closeEditor();
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
    $('#ed-save').disabled = false;
  }
}

async function removePost(slug, label) {
  if (busy) return;
  busy = true;
  try {
    await api('/api/posts/' + encodeURIComponent(slug) + '/delete', {});
    posts = posts.filter(p => p.slug !== slug);
    selected.delete(slug);
    counts();
    render();
    message('Deleted "' + (label || slug) + '".');
    closeEditor();
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
  }
}

/* Bulk */
async function bulk(action, button) {
  if (busy || !selected.size) return;
  const slugs = [...selected];
  if (action === 'clear') { selected.clear(); render(); return; }
  if (button.dataset.confirmed !== 'yes') {
    button.dataset.confirmed = 'yes';
    const verb = action === 'delete' ? 'DELETE' : action.toUpperCase();
    button.textContent = 'Confirm ' + verb + ' ' + slugs.length;
    message('Click again to ' + action + ' ' + slugs.length + ' article' + (slugs.length === 1 ? '' : 's') + '.');
    return;
  }
  busy = true;
  try {
    const result = await api('/api/bulk', {slugs: slugs, action: action});
    posts = action === 'delete' ? posts.filter(p => slugs.indexOf(p.slug) === -1) : posts;
    selected.clear();
    counts();
    render();
    message(result.summary || 'Done.');
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
  }
}

/* Wiring */
document.querySelectorAll('[data-filter]').forEach(b => b.onclick = () => {
  filter = b.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  render();
});
$('#blog-search').oninput = render;
$('#select-all').onchange = event => {
  const list = visible();
  if (event.target.checked) list.forEach(p => selected.add(p.slug));
  else list.forEach(p => selected.delete(p.slug));
  render();
};
document.querySelectorAll('[data-bulk]').forEach(b => b.onclick = () => bulk(b.dataset.bulk, b));
$('#new-post').onclick = () => openEditor(null);
$('#ed-save').onclick = save;
$('#ed-cancel').onclick = closeEditor;
$('#ed-preview').onclick = () => {
  const slug = editing || $('#f-slug').value.trim();
  if (slug) window.open('/manage/blog/preview/' + encodeURIComponent(slug), '_blank', 'noopener');
};
$('#ed-delete').onclick = event => {
  const button = event.currentTarget;
  const post = posts.find(p => p.slug === editing);
  if (!post) return;
  if (button.dataset.confirmed !== 'yes') {
    button.dataset.confirmed = 'yes';
    button.textContent = 'Confirm delete';
    message('Click again to delete "' + post.title + '". This removes it from the site.');
    return;
  }
  removePost(post.slug, post.title);
};
$('#faq-add').onclick = () => { if ($('#f-faq').children.length < 6) $('#f-faq').appendChild(faqRow()); };
['#f-title', '#f-seo', '#f-meta', '#f-content'].forEach(sel => {
  $(sel).addEventListener('input', countsUpdate);
});
$('#f-title').addEventListener('input', () => {
  if (editing) return;
  const slugField = $('#f-slug');
  if (!slugField.dataset.touched) slugField.value = slugify($('#f-title').value);
});
$('#f-slug').addEventListener('input', event => { event.target.dataset.touched = 'yes'; });
$('#f-cover').addEventListener('input', event => {
  const v = event.target.value.trim();
  $('#f-cover-preview').src = v ? (v.startsWith('http') ? v : '/' + v.replace(/^\/+/, '')) : '';
});

(async function start() {
  try {
    const data = await api('/api/posts');
    csrf = data.csrf;
    posts = data.posts || [];
    counts();
    render();
  } catch (error) {
    message(error.message, true);
  }
})();
