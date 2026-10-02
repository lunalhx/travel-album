/* Management is enabled only by the local editor server, never by a published page. */
(() => {
  if (!window.ALBUM_EDITABLE) return;
  let archive, selectedAlbumId, busy = false;
  const selectedPhotos = new Set();
  const $ = id => document.getElementById(id);
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(text, callback, className = '') {
    const node = element('button', className, text);
    node.type = 'button'; node.onclick = callback;
    return node;
  }
  function bytes(value) {
    return value < 1048576 ? (value / 1024).toFixed(0) + ' KB' : (value / 1048576).toFixed(2) + ' MB';
  }
  function albums() { return archive.manifest.albums; }
  function chosenAlbum() { return albums().find(a => a.id === selectedAlbumId); }
  function days(album) {
    return [...new Set([...(album.sessions || []), ...album.photos.map(p => p.shotAt.slice(0, 10))])].sort();
  }
  function status(text, error = false) {
    $('managerStatus').textContent = text;
    $('managerStatus').classList.toggle('error', error);
  }
  async function request(body, path = '/api/action', raw = false) {
    const response = await fetch(path, {method: 'POST', headers: {
      'X-Album-Token': archive.token,
      'Content-Type': raw ? 'application/octet-stream' : 'application/json'
    }, body: raw ? body : JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '保存失败，请重试。');
    return result;
  }
  function apply(result, choose = selectedAlbumId) {
    archive = result;
    selectedAlbumId = albums().some(a => a.id === choose) ? choose : albums()[0]?.id;
    selectedPhotos.clear();
    window.applyArchiveState(archive.manifest, archive.notes);
    render();
  }
  async function action(body) {
    if (busy) return;
    busy = true; status('正在保存…');
    try {
      const result = await request(body);
      apply(result, result.selectedAlbumId || selectedAlbumId);
      status('已保存到这台电脑。原图仍保留在你的文件夹中。');
      return true;
    } catch (error) { status(error.message, true); throw error; }
    finally { busy = false; }
  }
  function selectionBar(album, mount) {
    const bar = element('div', 'manager-selection');
    const count = element('span', '', '已选择 ' + selectedPhotos.size + ' 张');
    bar.append(count, button('全选', () => {album.photos.forEach(p => selectedPhotos.add(p.id)); render();}),
      button('取消选择', () => {selectedPhotos.clear(); render();}));
    const remove = button('移除所选照片', () => confirmAction('移除 ' + selectedPhotos.size + ' 张照片？',
      '从这本相册移除。你本地文件夹中的原图会保留，其他相册中的同一张照片也会保留。',
      {action: 'removePhotos', albumId: album.id, photoIds: [...selectedPhotos]}), 'manager-remove manager-danger');
    remove.disabled = !selectedPhotos.size;
    bar.append(remove); mount.append(bar);
  }
  function render() {
    const sidebar = $('managerAlbums'); sidebar.replaceChildren();
    $('managerAlbumCount').textContent = albums().length;
    albums().forEach(album => {
      const node = button('', () => {if (busy) return; selectedAlbumId = album.id; selectedPhotos.clear(); render();},
        'manager-album' + (album.id === selectedAlbumId ? ' active' : ''));
      node.append(element('strong', '', album.title), element('small', '', album.photos.length + ' 张照片 · ' + days(album).length + ' 次拍摄'));
      sidebar.append(node);
    });
    sidebar.append(button('＋ 新建相册', () => albumForm(), 'manager-new-album'));
    const info = $('managerStorage'); info.replaceChildren();
    info.append(element('strong', '', '轻量照片 ' + bytes(archive.storage?.photoBytes || 0)),
      document.createTextNode('网站只发布压缩副本。原图留在你的本地文件夹中。'));
    $('managerUndo').disabled = !archive.canUndo;
    const workspace = $('managerWorkspace'); workspace.replaceChildren();
    const album = chosenAlbum();
    if (!album) {
      workspace.append(element('div', 'manager-empty', '还没有相册。从「新建相册」开始，收好第一段记忆。'));
      return;
    }
    const top = element('div', 'manager-workspace-top');
    const title = element('div'); title.append(element('h3', '', album.title),
      element('p', '', album.tag + ' · ' + album.photos.length + ' 张照片 · ' + days(album).length + ' 次拍摄'));
    const settings = element('div', 'manager-album-actions');
    settings.append(button('相册设置', () => albumForm(album)), button('删除相册', () => confirmAction('删除这本相册？',
      '「' + album.title + '」的相册记录、日期和手记将移除，原图会保留。删除后可以撤销。',
      {action: 'deleteAlbum', albumId: album.id}), 'manager-danger'));
    top.append(title, settings); workspace.append(top);
    const actions = element('div', 'manager-day-actions');
    actions.append(button('＋ 添加照片', () => importForm(album), 'manager-button primary'),
      button('＋ 新增拍摄日期', () => dateForm(album), 'manager-button'));
    workspace.append(actions); selectionBar(album, workspace);
    if (!days(album).length) workspace.append(element('div', 'manager-empty', '相册已经建好。添加照片，或者先记下一个拍摄日期。'));
    days(album).forEach(day => {
      const photos = album.photos.filter(p => p.shotAt.slice(0, 10) === day);
      const section = element('section', 'manager-day');
      const heading = element('div', 'manager-day-top');
      const label = element('div', 'manager-day-title');
      label.append(element('h4', '', day.replaceAll('-', '.')), element('small', '', photos.length + ' 张'));
      const controls = element('div', 'manager-day-controls');
      controls.append(button('添加照片', () => importForm(album, day)), button('修改日期', () => dateForm(album, day)),
        button('移除日期', () => confirmAction('移除 ' + day.replaceAll('-', '.') + '？',
          '这次拍摄的 ' + photos.length + ' 张照片和手记会从这本相册移除，原图会保留。',
          {action: 'deleteDate', albumId: album.id, date: day}), 'manager-danger'));
      heading.append(label, controls); section.append(heading);
      if (!photos.length) section.append(element('div', 'manager-empty', '这一天还没有照片，可以稍后添加。'));
      else {
        const grid = element('div', 'manager-photo-grid');
        photos.forEach(photo => {
          const item = element('div', 'manager-photo');
          const label = element('label', 'manager-photo-label');
          const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.checked = selectedPhotos.has(photo.id);
          checkbox.setAttribute('aria-label', '选择 ' + photo.filename);
          checkbox.onchange = () => {checkbox.checked ? selectedPhotos.add(photo.id) : selectedPhotos.delete(photo.id); render();};
          const img = element('img'); img.src = photo.thumb || photo.src; img.alt = photo.caption; img.loading = 'lazy';
          label.append(checkbox, img); item.append(label);
          const meta = element('div', 'manager-photo-info'); const name = element('span', '', photo.filename); name.title = photo.filename;
          const edit = button('编辑', () => photoForm(album, photo)); edit.setAttribute('aria-label', '编辑 ' + photo.filename);
          meta.append(name, edit); item.append(meta); grid.append(item);
        });
        section.append(grid);
      }
      workspace.append(section);
    });
  }
  function makeForm(title, intro) {
    if (busy) return null;
    const mount = $('managerFormMount'); mount.replaceChildren();
    const heading = element('div', 'manager-form-top');
    heading.append(element('h3', '', title), button('×', () => $('managerFormDialog').close()));
    heading.lastChild.setAttribute('aria-label', '关闭管理表单');
    mount.append(heading, element('p', 'manager-form-intro', intro));
    const form = element('form', 'manager-form');
    const fields = element('div'); form.append(fields);
    const message = element('p', 'manager-form-message'); message.setAttribute('role', 'status');
    const actions = element('div', 'manager-form-actions');
    actions.append(button('取消', () => $('managerFormDialog').close()));
    const save = element('button', 'manager-button primary', '保存'); save.type = 'submit'; actions.append(save);
    form.append(message, actions); mount.append(form);
    $('managerFormDialog').showModal();
    return {form, fields, message, save};
  }
  function field(mount, text, type, value = '', name = '') {
    const label = element('label', '', text);
    const input = element(type === 'select' ? 'select' : 'input');
    if (type !== 'select') input.type = type;
    if (type !== 'select') input.value = value;
    input.name = name; input.required = true; label.append(input); mount.append(label);
    return input;
  }
  function option(select, text, value) {const item = element('option', '', text); item.value = value; select.append(item);}
  function submit(form, callback) {
    form.form.onsubmit = async event => {
      event.preventDefault(); if (busy) return; form.save.disabled = true;
      try {await callback(); $('managerFormDialog').close();}
      catch (error) {form.message.textContent = error.message; form.message.classList.add('error');}
      finally {form.save.disabled = false;}
    };
  }
  function albumForm(album) {
    const form = makeForm(album ? '相册设置' : '新建一本相册', '同年同城的照片收进一本相册，完整旅行也可以独立成册。');
    if (!form) return;
    const grid = element('div', 'manager-form-grid'); form.fields.append(grid);
    const kind = field(grid, '相册类型', 'select'); option(kind, '城市年度相册', 'annual'); option(kind, '独立旅行相册', 'special'); kind.value = album?.albumType || 'annual';
    const year = field(grid, '年份', 'number', album?.year || String(new Date().getFullYear())); year.min = '1900'; year.max = '2100';
    const city = field(grid, '城市', 'text', album?.city || ''); city.maxLength = 60; city.placeholder = '例如：兰州';
    const region = field(grid, '所属地区', 'select'); option(region, '选择地区', '');
    archive.provinces.forEach(p => option(region, p.name, p.code)); region.value = album?.provinceCode || '';
    const title = field(form.fields, '相册名称（选填）', 'text', album?.title || ''); title.required = false; title.maxLength = 120; title.placeholder = '留空会使用「年份 · 城市」';
    submit(form, () => action({action: album ? 'updateAlbum' : 'createAlbum', albumId: album?.id,
      city: city.value, provinceCode: region.value, year: year.value, albumType: kind.value, title: title.value}));
  }
  function defaultDate(album) {
    const now = new Date(), today = [now.getFullYear(), String(now.getMonth()+1).padStart(2,'0'), String(now.getDate()).padStart(2,'0')].join('-');
    return days(album).at(-1) || (today.startsWith(album.year) ? today : album.year + '-01-01');
  }
  function dateForm(album, day) {
    const form = makeForm(day ? '修改拍摄日期' : '新增拍摄日期', day ? '照片和当天的手记会一起移到新的日期。' : '可以先记下日期，再慢慢添加照片与手记。');
    if (!form) return;
    const input = field(form.fields, '拍摄日期', 'date', day || defaultDate(album));
    submit(form, () => action({action: day ? 'editDate' : 'addDate', albumId: album.id, date: day || input.value, newDate: input.value}));
  }
  function photoForm(album, photo) {
    const form = makeForm('编辑照片资料', '修改这张照片在相册里的日期和说明。'); if (!form) return;
    const day = field(form.fields, '拍摄日期', 'date', photo.shotAt.slice(0,10));
    const caption = field(form.fields, '照片说明', 'text', photo.caption); caption.maxLength = 300; caption.required = false;
    submit(form, () => action({action: 'editPhoto', albumId: album.id, photoId: photo.id, date: day.value, caption: caption.value}));
  }
  function confirmAction(title, text, body) {
    const form = makeForm(title, text); if (!form) return;
    form.save.textContent = '确认移除'; form.save.classList.add('danger');
    submit(form, () => action(body));
  }
  function importForm(album, day) {
    const form = makeForm('添加照片', '从你的文件夹选择照片。自动生成最长边 1280px 的 WebP 轻量副本，完整原图继续保留在电脑上。');
    if (!form) return;
    const date = field(form.fields, '这次拍摄的日期', 'date', day || defaultDate(album));
    const input = field(form.fields, '选择照片（可多选）', 'file'); input.multiple = true; input.accept = 'image/jpeg,image/png,image/webp';
    let pending = [], added = 0, batchId = crypto.randomUUID();
    input.onchange = () => {pending = [...input.files]; added = 0; batchId = crypto.randomUUID(); form.message.textContent = '已选择 ' + pending.length + ' 张 · 原文件 ' + bytes(pending.reduce((sum,f) => sum+f.size,0)); form.message.classList.remove('error');};
    form.save.textContent = '生成缩略图并添加';
    submit(form, async () => {
      if (!pending.length) throw new Error('请先选择照片。');
      busy = true;
      try {
        const total = pending.length + added;
        while (pending.length) {
          const file = pending[0];
          form.message.textContent = '正在生成缩略图 ' + (added+1) + ' / ' + total + '…';
          const query = new URLSearchParams({albumId: album.id, date: date.value, filename: file.name, batchId});
          const result = await request(file, '/api/photos?' + query, true);
          pending.shift(); added++; apply(result, album.id);
        }
        status('已添加 ' + added + ' 张照片，只保存了轻量副本。');
      } catch(error) {throw new Error('已添加 ' + added + ' 张。' + error.message);}
      finally {busy = false;}
    });
  }
  async function open(albumId) {
    if (!archive) return;
    selectedAlbumId = albumId || selectedAlbumId || albums()[0]?.id;
    selectedPhotos.clear(); render(); $('archiveManager').showModal(); document.body.classList.add('notes-open');
  }
  window.openArchiveManager = open;
  window.saveArchiveNote = async (key, note) => {
    const slash = key.lastIndexOf('/');
    const result = await request({action: 'saveNote', albumId: key.slice(0,slash), date: key.slice(slash+1), note});
    apply(result); return result.notes;
  };
  document.addEventListener('DOMContentLoaded', () => {
    $('managerClose').onclick = () => $('archiveManager').close();
    $('archiveManager').addEventListener('close', () => document.body.classList.remove('notes-open'));
    $('managerFormDialog').addEventListener('cancel', event => {if (busy) event.preventDefault();});
    $('managerUndo').onclick = () => action({action: 'undo'}).catch(() => {});
    $('managerViewAlbum').onclick = () => {
      const index = window.getArchiveAlbums().findIndex(a => a.id === selectedAlbumId);
      if (index >= 0) { $('archiveManager').close(); window.showArchiveAlbum(index); }
    };
    $('managerExport').onclick = async () => {
      if (busy) return; busy = true; status('正在整理发布包…');
      try {
        const response = await fetch('/api/export', {headers: {'X-Album-Token': archive.token}});
        if (!response.ok) throw new Error((await response.json()).error);
        const blob = await response.blob(), url = URL.createObjectURL(blob);
        const link = element('a'); link.href = url; link.download = 'travel-album-site.zip'; document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
        status('发布包已下载 · ' + bytes(blob.size) + '。解压后可提交到 GitHub。');
      } catch(error) {status(error.message, true);}
      finally {busy = false;}
    };
  });
  window.initializeArchiveManager = result => {archive = result; document.documentElement.classList.add('archive-editable');};
})();
