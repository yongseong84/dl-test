(function () {
  'use strict';

  var KEY_STORAGE = 'corpcardAudit.kakaoJsKey';

  var state = {
    employees: EMPLOYEES.map(function (e) { return Object.assign({}, e); }),
    transactions: TRANSACTIONS.map(function (t) { return Object.assign({}, t); }),
    threshold: 500,
    empFilter: 'all',
    flagFilter: 'all',
    search: '',
    sortKey: 'No',
    sortDir: 1,
    map: null,
    markers: [],
    circles: [],
    infoWindow: null,
  };

  var empById = {};
  state.employees.forEach(function (e) { empById[e.id] = e; });

  // ---------- Geo helpers ----------
  function haversine(lat1, lng1, lat2, lng2) {
    var R = 6371000;
    var toRad = function (d) { return (d * Math.PI) / 180; };
    var dLat = toRad(lat2 - lat1);
    var dLng = toRad(lng2 - lng1);
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function recompute() {
    state.transactions.forEach(function (tx) {
      var emp = empById[tx.EmployeeId];
      if (!emp || emp.homeLat == null || emp.homeLng == null) {
        tx._distance = null;
        tx._flagged = false;
        return;
      }
      var d = haversine(emp.homeLat, emp.homeLng, tx.Lat, tx.Lng);
      tx._distance = Math.round(d);
      tx._flagged = d <= state.threshold;
    });
  }

  function fmtMoney(n) { return n.toLocaleString('ko-KR') + '원'; }
  function fmtDist(tx) { return tx._distance == null ? '-' : tx._distance.toLocaleString('ko-KR') + 'm'; }

  // ---------- Filtering / sorting ----------
  function filteredTransactions() {
    return state.transactions.filter(function (tx) {
      if (state.empFilter !== 'all' && tx.EmployeeId !== state.empFilter) return false;
      if (state.flagFilter === 'flagged' && !tx._flagged) return false;
      if (state.flagFilter === 'normal' && tx._flagged) return false;
      if (state.search && tx.MerchantName.toLowerCase().indexOf(state.search.toLowerCase()) === -1) return false;
      return true;
    }).sort(function (a, b) {
      var key = state.sortKey;
      var va = key === 'distance' ? (a._distance == null ? Infinity : a._distance) : key === 'flagged' ? (a._flagged ? 1 : 0) : a[key];
      var vb = key === 'distance' ? (b._distance == null ? Infinity : b._distance) : key === 'flagged' ? (b._flagged ? 1 : 0) : b[key];
      if (va < vb) return -1 * state.sortDir;
      if (va > vb) return 1 * state.sortDir;
      return 0;
    });
  }

  // ---------- Rendering ----------
  function renderSummary() {
    var all = state.transactions;
    var flagged = all.filter(function (t) { return t._flagged; });
    var flaggedAmount = flagged.reduce(function (s, t) { return s + t.TransactionAmount; }, 0);
    var flaggedUsers = new Set(flagged.map(function (t) { return t.EmployeeId; }));

    var cards = [
      { label: '전체 거래 건수', value: all.length + '건' },
      { label: '자택인근 의심 건수', value: flagged.length + '건', alert: true, sub: '판정 반경 ' + state.threshold + 'm 기준' },
      { label: '의심 거래 금액 합계', value: fmtMoney(flaggedAmount), alert: flaggedAmount > 0 },
      { label: '의심 대상 임직원 수', value: flaggedUsers.size + '명 / ' + state.employees.length + '명' },
    ];

    var html = cards.map(function (c) {
      return (
        '<div class="summary-card">' +
        '<div class="summary-card__label">' + c.label + '</div>' +
        '<div class="summary-card__value' + (c.alert ? ' is-alert' : '') + '">' + c.value + '</div>' +
        (c.sub ? '<div class="summary-card__sub">' + c.sub + '</div>' : '') +
        '</div>'
      );
    }).join('');
    document.getElementById('summary').innerHTML = html;
  }

  function renderEmpFilterOptions() {
    var sel = document.getElementById('empFilter');
    var html = '<option value="all">전체 임직원</option>';
    state.employees.forEach(function (e) {
      var flaggedCount = state.transactions.filter(function (t) { return t.EmployeeId === e.id && t._flagged; }).length;
      html += '<option value="' + e.id + '">' + e.name + ' (' + e.title + ')' + (flaggedCount ? ' ⚠ ' + flaggedCount : '') + '</option>';
    });
    sel.innerHTML = html;
    sel.value = state.empFilter;
  }

  function renderEmpTable() {
    var tbody = document.querySelector('#empTable tbody');
    tbody.innerHTML = state.employees.map(function (e) {
      return (
        '<tr>' +
        '<td>' + e.id + '</td>' +
        '<td>' + e.name + '</td>' +
        '<td>' + e.title + '</td>' +
        '<td>' + e.dept + '</td>' +
        '<td>' + e.card + '</td>' +
        '<td><input class="home-addr-input" data-emp="' + e.id + '" value="' + e.homeAddress + '" /></td>' +
        '</tr>'
      );
    }).join('');

    tbody.querySelectorAll('.home-addr-input').forEach(function (input) {
      input.addEventListener('change', function () {
        var emp = empById[input.dataset.emp];
        emp.homeAddress = input.value;
        geocodeEmployeeHome(emp, function () {
          recompute();
          renderAll();
        });
      });
    });
  }

  function renderTable() {
    var rows = filteredTransactions();
    document.getElementById('rowCount').textContent = rows.length + '건 표시 중 (전체 ' + state.transactions.length + '건)';
    var tbody = document.getElementById('txTableBody');
    tbody.innerHTML = rows.map(function (tx) {
      return (
        '<tr class="' + (tx._flagged ? 'is-flagged' : '') + '" data-no="' + tx.No + '">' +
        '<td>' + tx.No + '</td>' +
        '<td>' + tx.UserName + '</td>' +
        '<td>' + tx.TransactionDate + ' ' + tx.ApprovalTime + '</td>' +
        '<td>' + tx.MerchantName + '</td>' +
        '<td>' + tx.MerchantAddress + '</td>' +
        '<td>' + tx.MerchantIndustryName + '</td>' +
        '<td>' + tx.UsageType + '</td>' +
        '<td>' + fmtMoney(tx.TransactionAmount) + '</td>' +
        '<td>' + fmtDist(tx) + '</td>' +
        '<td>' + (tx._flagged ? '<span class="pill pill--flag">자택인근 의심</span>' : '<span class="pill pill--normal">정상</span>') + '</td>' +
        '</tr>'
      );
    }).join('');

    tbody.querySelectorAll('tr').forEach(function (tr) {
      tr.addEventListener('click', function () {
        var no = parseInt(tr.dataset.no, 10);
        var tx = state.transactions.find(function (t) { return t.No === no; });
        if (tx) focusOnMap(tx);
      });
    });
  }

  function renderAll() {
    recompute();
    renderSummary();
    renderEmpFilterOptions();
    renderTable();
    if (state.map) renderMapMarkers();
  }

  // ---------- Kakao Map ----------
  function loadKakaoSDK(key) {
    return new Promise(function (resolve, reject) {
      if (window.kakao && window.kakao.maps) return resolve();
      var script = document.createElement('script');
      script.src = 'https://dapi.kakao.com/v2/maps/sdk.js?appkey=' + encodeURIComponent(key) + '&libraries=services&autoload=false';
      script.onload = function () { window.kakao.maps.load(resolve); };
      script.onerror = function () { reject(new Error('카카오맵 SDK 로드에 실패했습니다. 키 또는 도메인 등록을 확인하세요.')); };
      document.head.appendChild(script);
    });
  }

  function initMap() {
    var container = document.getElementById('map');
    state.map = new kakao.maps.Map(container, {
      center: new kakao.maps.LatLng(37.5175, 127.0473),
      level: 7,
    });
    state.infoWindow = new kakao.maps.InfoWindow({ removable: true });
    document.querySelector('.map-panel').classList.add('has-map');
    renderMapMarkers();
  }

  function clearMapOverlays() {
    state.markers.forEach(function (m) { m.setMap(null); });
    state.circles.forEach(function (c) { c.setMap(null); });
    state.markers = [];
    state.circles = [];
  }

  function makeDotMarkerImage(color) {
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22">' +
      '<circle cx="11" cy="11" r="8" fill="' + color + '" stroke="#fff" stroke-width="2"/>' +
      '</svg>';
    var url = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg);
    return new kakao.maps.MarkerImage(url, new kakao.maps.Size(22, 22), { offset: new kakao.maps.Point(11, 11) });
  }

  function makeHomeMarkerImage() {
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28">' +
      '<circle cx="14" cy="14" r="11" fill="#d4af37" stroke="#a9841f" stroke-width="2"/>' +
      '<text x="14" y="19" font-size="13" text-anchor="middle" fill="#1b1400">★</text>' +
      '</svg>';
    var url = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg);
    return new kakao.maps.MarkerImage(url, new kakao.maps.Size(28, 28), { offset: new kakao.maps.Point(14, 14) });
  }

  function renderMapMarkers() {
    if (!state.map) return;
    clearMapOverlays();

    var employeesToShow = state.empFilter === 'all' ? state.employees : state.employees.filter(function (e) { return e.id === state.empFilter; });
    var bounds = new kakao.maps.LatLngBounds();
    var homeImg = makeHomeMarkerImage();

    employeesToShow.forEach(function (e) {
      if (e.homeLat == null || e.homeLng == null) return;
      var pos = new kakao.maps.LatLng(e.homeLat, e.homeLng);
      var marker = new kakao.maps.Marker({ position: pos, image: homeImg, map: state.map, zIndex: 10 });
      kakao.maps.event.addListener(marker, 'click', function () {
        state.infoWindow.setContent('<div style="padding:6px 10px;font-size:12px;">🏠 ' + e.name + ' 자택<br>' + e.homeAddress + '</div>');
        state.infoWindow.open(state.map, marker);
      });
      state.markers.push(marker);

      var circle = new kakao.maps.Circle({
        center: pos,
        radius: state.threshold,
        strokeWeight: 1,
        strokeColor: '#d4af37',
        strokeOpacity: 0.7,
        fillColor: '#d4af37',
        fillOpacity: 0.12,
        map: state.map,
      });
      state.circles.push(circle);
      bounds.extend(pos);
    });

    var rows = filteredTransactions();
    var flagImg = makeDotMarkerImage('#d64545');
    var normalImg = makeDotMarkerImage('#7891ac');

    rows.forEach(function (tx) {
      if (tx.Lat == null || tx.Lng == null) return;
      var pos = new kakao.maps.LatLng(tx.Lat, tx.Lng);
      var marker = new kakao.maps.Marker({ position: pos, image: tx._flagged ? flagImg : normalImg, map: state.map });
      kakao.maps.event.addListener(marker, 'click', function () {
        state.infoWindow.setContent(
          '<div style="padding:6px 10px;font-size:12px;">' +
          '<strong>' + tx.MerchantName + '</strong><br>' +
          tx.MerchantAddress + '<br>' +
          tx.UserName + ' · ' + tx.TransactionDate + ' · ' + fmtMoney(tx.TransactionAmount) + '<br>' +
          '자택거리: ' + fmtDist(tx) +
          (tx._flagged ? ' <span style="color:#d64545;font-weight:700;">(의심)</span>' : '') +
          '</div>'
        );
        state.infoWindow.open(state.map, marker);
      });
      state.markers.push(marker);
      bounds.extend(pos);
    });

    if (!bounds.isEmpty()) state.map.setBounds(bounds);
  }

  function focusOnMap(tx) {
    if (!state.map || tx.Lat == null) return;
    var pos = new kakao.maps.LatLng(tx.Lat, tx.Lng);
    state.map.setCenter(pos);
    state.map.setLevel(4);
    state.infoWindow.setContent(
      '<div style="padding:6px 10px;font-size:12px;"><strong>' + tx.MerchantName + '</strong><br>' + tx.MerchantAddress + '<br>자택거리: ' + fmtDist(tx) + '</div>'
    );
    state.infoWindow.open(state.map, new kakao.maps.Marker({ position: pos }));
  }

  function geocodeEmployeeHome(emp, cb) {
    if (!(window.kakao && window.kakao.maps && window.kakao.maps.services)) {
      alert('카카오맵 키가 설정되지 않아 주소를 좌표로 변환할 수 없습니다. 기존 좌표가 유지됩니다.\n키 설정 후 다시 시도해 주세요.');
      cb();
      return;
    }
    var geocoder = new kakao.maps.services.Geocoder();
    geocoder.addressSearch(emp.homeAddress, function (result, status) {
      if (status === kakao.maps.services.Status.OK && result[0]) {
        emp.homeLat = parseFloat(result[0].y);
        emp.homeLng = parseFloat(result[0].x);
      } else {
        alert(emp.name + '의 주소를 좌표로 변환하지 못했습니다. 도로명주소 형식을 확인하세요. (기존 좌표 유지)');
      }
      cb();
    });
  }

  // ---------- CSV export ----------
  function exportCSV() {
    var rows = filteredTransactions().filter(function (t) { return t._flagged; });
    if (!rows.length) { alert('내보낼 자택인근 의심 거래가 없습니다.'); return; }
    var headers = ['No', 'UserName', 'CardNumber', 'TransactionDate', 'ApprovalTime', 'MerchantName', 'MerchantAddress', 'UsageType', 'TransactionAmount', 'Distance(m)'];
    var lines = [headers.join(',')];
    rows.forEach(function (t) {
      var line = [t.No, t.UserName, t.CardNumber, t.TransactionDate, t.ApprovalTime, t.MerchantName, '"' + t.MerchantAddress.replace(/"/g, '""') + '"', t.UsageType, t.TransactionAmount, t._distance];
      lines.push(line.join(','));
    });
    var blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = '자택인근사용_의심내역_' + Date.now() + '.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------- Wiring ----------
  function setKeyStatus(ok) {
    var el = document.getElementById('keyStatus');
    el.textContent = ok ? '연결됨' : '미설정';
    el.classList.toggle('is-ok', ok);
  }

  function tryLoadStoredKey() {
    var key = localStorage.getItem(KEY_STORAGE);
    if (!key) return;
    document.getElementById('kakaoKeyInput').value = key;
    loadKakaoSDK(key).then(function () {
      setKeyStatus(true);
      initMap();
    }).catch(function (err) {
      setKeyStatus(false);
      console.error(err);
    });
  }

  document.getElementById('saveKeyBtn').addEventListener('click', function () {
    var key = document.getElementById('kakaoKeyInput').value.trim();
    if (!key) { alert('카카오 JavaScript 키를 입력하세요.'); return; }
    localStorage.setItem(KEY_STORAGE, key);
    loadKakaoSDK(key).then(function () {
      setKeyStatus(true);
      initMap();
    }).catch(function (err) {
      setKeyStatus(false);
      alert(err.message);
    });
  });

  document.getElementById('clearKeyBtn').addEventListener('click', function () {
    localStorage.removeItem(KEY_STORAGE);
    document.getElementById('kakaoKeyInput').value = '';
    setKeyStatus(false);
    location.reload();
  });

  document.getElementById('empFilter').addEventListener('change', function (e) {
    state.empFilter = e.target.value;
    renderTable();
    if (state.map) renderMapMarkers();
  });

  document.getElementById('radiusFilter').addEventListener('change', function (e) {
    state.threshold = parseInt(e.target.value, 10);
    renderAll();
  });

  document.getElementById('flagFilter').addEventListener('change', function (e) {
    state.flagFilter = e.target.value;
    renderTable();
  });

  document.getElementById('searchInput').addEventListener('input', function (e) {
    state.search = e.target.value;
    renderTable();
  });

  document.getElementById('exportBtn').addEventListener('click', exportCSV);

  document.querySelectorAll('#txTable thead th[data-sort]').forEach(function (th) {
    th.addEventListener('click', function () {
      var key = th.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir *= -1;
      } else {
        state.sortKey = key;
        state.sortDir = 1;
      }
      renderTable();
    });
  });

  // ---------- Init ----------
  renderEmpTable();
  renderAll();
  tryLoadStoredKey();
})();
