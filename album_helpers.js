/* Shared album grouping/navigation logic; no photo-viewer state is changed here. */
const AlbumHelpers = (() => {
  function groupPhotoDays(order, photos, dates = []) {
    const groups = new Map();
    dates.forEach(date => groups.set(date, {date, items: []}));
    order.forEach((photoId, albumPosition) => {
      const date = photos[photoId].shotAt?.slice(0, 10) || '未注明日期';
      if (!groups.has(date)) groups.set(date, {date, items: []});
      groups.get(date).items.push({photoId, albumPosition});
    });
    return [...groups.values()].sort((a, b) => a.date.localeCompare(b.date));
  }

  function regionAlbumIndexes(albums, provinceCode) {
    return albums.map((album, index) => ({album, index}))
      .filter(({album}) => String(album.provinceCode) === String(provinceCode))
      .sort((a, b) => (b.album.dateEnd || b.album.year || '').localeCompare(a.album.dateEnd || a.album.year || '') || a.index - b.index)
      .map(({index}) => index);
  }

  function nextAlbumOffset(current, delta, count) {
    return count ? Math.max(0, Math.min(count - 1, current + delta)) : 0;
  }

  return {groupPhotoDays, regionAlbumIndexes, nextAlbumOffset};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = AlbumHelpers;
