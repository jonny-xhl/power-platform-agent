/**
 * contact_list.js — behavior for the embedded Contact List HTML page (HKL CCRM Page 21).
 *
 * Embedded in the Account form "Contact" tab (PassParams=1). Reads the current account id
 * from the URL, queries that account's contacts via Xrm.WebApi, and renders a table:
 * Name | Email | HKL PIC | Title | Latest Meeting | Feedback.
 *
 * Dependencies: XRM.Common.js (loaded before this script). Goes through XRM.Common for
 * data/navigation/util per project convention (no raw Xrm except the PassParams URL read).
 */
(function (window, document, undefined) {
    'use strict';

    var ContactList = (window.ContactList = window.ContactList || {});

    // ---- DOM refs ----
    var tbody, emptyState, searchInput, newContactBtn, refreshEl, paginationEl, summaryBtn;

    // ---- state ----
    var allContacts = [];   // last-loaded full set
    var accountId = null;
    var accountEntity = 'account';

    // ============================================================ utils

    function _escape(value) {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function _formatTime(date) {
        var h = date.getHours(), m = date.getMinutes();
        var ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12;
        if (h === 0) h = 12;
        return (h < 10 ? '0' + h : h) + ':' + (m < 10 ? '0' + m : m) + ' ' + ampm;
    }

    function _formatDate(iso) {
        if (!iso) return '';
        var d = new Date(iso);
        if (isNaN(d.getTime())) return '';
        var y = d.getFullYear();
        var mo = String(d.getMonth() + 1).padStart(2, '0');
        var da = String(d.getDate()).padStart(2, '0');
        return y + '-' + mo + '-' + da;
    }

    function _getAccountId() {
        // PassParams appends id/typename/type/orgname/userlcid to the page URL.
        var params = new URLSearchParams(window.location.search);
        var id = params.get('id');
        if (id) return id;
        // Fallback: `data` param (openWebResource(data="id=...")).
        var data = params.get('data');
        if (data) {
            var kv = new URLSearchParams(data);
            return kv.get('id');
        }
        return null;
    }

    function _getXrm() {
        // Embedded web-resource iframe: XRM.Common.js captures `Xrm` at ITS load time, which is
        // undefined inside an iframe — so XRM.Common.Nav/Data are unusable here. Resolve Xrm
        // ourselves (parent form → top → window) and use it directly for both data and navigation.
        var x = (window.parent && window.parent.Xrm) || (window.top && window.top.Xrm) || window.Xrm;
        if (x) window.Xrm = x;
        return x;
    }

    // ============================================================ data

    function _hklPicName(c) {
        // Prefer the $expand navigation object, then the OData formatted value, then "—".
        if (c['new_HklPic'] && c['new_HklPic'].fullname) return c['new_HklPic'].fullname;
        var fmt = c['_new_hklpic_value@OData.Community.Display.V1.FormattedValue'];
        if (fmt) return fmt;
        return '—';
    }

    function loadContacts() {
        accountId = _getAccountId();
        if (!accountId) {
            _renderEmpty('Open this page from an Account form to see its contacts.');
            return;
        }
        var xrm = _getXrm();
        if (!xrm || !xrm.WebApi) {
            _renderEmpty('Xrm context unavailable — embed this page in an Account form.');
            return;
        }
        var options =
            '?$select=firstname,lastname,emailaddress1,jobtitle,new_lastengagementdate' +
            '&$filter=_parentcustomerid_value eq ' + accountId +
            '&$expand=new_HklPic($select=fullname)';

        xrm.WebApi.retrieveMultipleRecords('contact', options).then(
            function (result) {
                allContacts = result.entities || [];
                _renderRows(allContacts);
                _updateLastRefresh();
            },
            function (err) {
                console.error('[ContactList] query failed', err);
                _renderEmpty('Failed to load contacts: ' + (err && err.message ? err.message : 'unknown error'));
            }
        );
    }

    // ============================================================ render

    function _rowHtml(c) {
        var first = c.firstname || '';
        var last = c.lastname || '';
        var name = (first + ' ' + last).trim() || '(unnamed)';
        var email = c.emailaddress1 || '';
        var pic = _hklPicName(c);
        var title = c.jobtitle || '';
        var meeting = _formatDate(c.new_lastengagementdate) || '—';
        var cid = c.contactid;

        var nameCell = cid
            ? '<span class="contact-list-name" data-cid="' + _escape(cid) + '">' + _escape(name) + '</span>'
            : _escape(name);
        var emailCell = email
            ? '<a href="mailto:' + _escape(email) + '">' + _escape(email) + '</a>'
            : '<span class="contact-list-muted">—</span>';

        return (
            '<tr>' +
            '<td class="contact-list-name-cell">' + nameCell + '</td>' +
            '<td class="contact-list-email">' + emailCell + '</td>' +
            '<td>' + _escape(pic) + '</td>' +
            '<td>' + _escape(title) + '</td>' +
            '<td>' + _escape(meeting) + '</td>' +
            '<td class="contact-list-muted">—</td>' +
            '</tr>'
        );
    }

    function _renderRows(contacts) {
        if (!contacts.length) {
            _renderEmpty('No contacts found for this tenant.');
            return;
        }
        emptyState.style.display = 'none';
        tbody.innerHTML = contacts.map(_rowHtml).join('');
        _wireRowClicks();
        _updatePagination(contacts.length, allContacts.length);
    }

    function _renderEmpty(message) {
        tbody.innerHTML = '';
        emptyState.textContent = message || 'No contacts found.';
        emptyState.style.display = 'block';
        _updatePagination(0, 0);
    }

    function _wireRowClicks() {
        var nodes = tbody.querySelectorAll('.contact-list-name[data-cid]');
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].addEventListener('click', _onNameClick);
        }
    }

    function _onNameClick(e) {
        var cid = e.currentTarget.getAttribute('data-cid');
        if (!cid) return;
        var xrm = _getXrm();
        if (xrm && xrm.Navigation) {
            xrm.Navigation.openForm({ entityName: 'contact', entityId: cid });
        }
    }

    // ============================================================ search

    function _applySearch() {
        var q = (searchInput.value || '').trim().toLowerCase();
        if (!q) {
            _renderRows(allContacts);
            return;
        }
        var filtered = allContacts.filter(function (c) {
            var name = ((c.firstname || '') + ' ' + (c.lastname || '')).toLowerCase();
            var email = (c.emailaddress1 || '').toLowerCase();
            var title = (c.jobtitle || '').toLowerCase();
            var pic = _hklPicName(c).toLowerCase();
            return name.indexOf(q) >= 0 || email.indexOf(q) >= 0 || title.indexOf(q) >= 0 || pic.indexOf(q) >= 0;
        });
        _renderRows(filtered);
    }

    // ============================================================ actions

    function _newContact() {
        if (!accountId) return;
        var xrm = _getXrm();
        // createFromEntity pre-populates parentcustomerid (Tenant) on the new contact.
        if (xrm && xrm.Navigation) {
            xrm.Navigation.openForm({
                entityName: 'contact',
                createFromEntity: { id: accountId, entityType: accountEntity },
            });
        }
    }

    function _updateLastRefresh() {
        refreshEl.textContent = _formatTime(new Date());
    }

    function _updatePagination(visible, total) {
        if (!visible) {
            paginationEl.textContent = 'Showing 0 to 0 of 0';
            return;
        }
        paginationEl.textContent = 'Showing 1 to ' + visible + ' of ' + total;
    }

    // ============================================================ init

    function init() {
        tbody = document.getElementById('contactTbody');
        emptyState = document.getElementById('emptyState');
        searchInput = document.getElementById('searchInput');
        newContactBtn = document.getElementById('newContactBtn');
        refreshEl = document.getElementById('lastRefresh');
        paginationEl = document.getElementById('paginationInfo');
        summaryBtn = document.getElementById('seeSummaryBtn');

        if (newContactBtn) newContactBtn.addEventListener('click', _newContact);
        if (searchInput) searchInput.addEventListener('input', _applySearch);
        if (summaryBtn) summaryBtn.addEventListener('click', function () { window.scrollTo(0, 0); });

        loadContacts();
    }

    ContactList.init = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window, document);
