/**
 * contact_tags.js — behavior for the Contact Tag pane (HKL CCRM Page 21).
 *
 * Embedded in the Contact form Summary tab (PassParams=1). Reads the current contact id
 * from the URL, queries that contact's new_ContactTag records via Xrm.WebApi, and renders
 * colored-circle rows: abbreviation | Tag name / sub-label / source. Goes through XRM.Common.
 */
(function (window, document, undefined) {
    'use strict';

    var ContactTag = (window.ContactTag = window.ContactTag || {});

    // new_Color optionset value -> circle background color.
    var COLOR_MAP = {
        100000000: '#e74c3c', // Red
        100000001: '#e67e22', // Orange
        100000002: '#f1c40f', // Yellow (dark text)
        100000003: '#2ecc71', // Green
        100000004: '#3498db', // Blue
        100000005: '#9b59b6', // Purple
    };

    var tagList, paginationEl, addTagBtn, contactId = null;

    function _escape(v) {
        if (v === null || v === undefined) return '';
        return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function _getContactId() {
        var params = new URLSearchParams(window.location.search);
        var id = params.get('id');
        if (id) return id;
        var data = params.get('data');
        return data ? new URLSearchParams(data).get('id') : null;
    }

    function _getXrm() {
        // Embedded iframe: XRM.Common captures Xrm at load (undefined here), so resolve it
        // ourselves (parent form → top → window) and use directly for data + navigation.
        var x = (window.parent && window.parent.Xrm) || (window.top && window.top.Xrm) || window.Xrm;
        if (x) window.Xrm = x;
        return x;
    }

    function _colorFor(value) {
        return COLOR_MAP[value] || '#605e5c';
    }

    function _initials(name, abbrev) {
        if (abbrev) return abbrev.slice(0, 2);
        if (!name) return '?';
        return name.replace(/[^A-Za-z0-9 ]/g, '').split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0]; }).join('').toUpperCase() || '?';
    }

    function loadTags() {
        contactId = _getContactId();
        if (!contactId) {
            _renderEmpty('Open this pane from a Contact form.');
            return;
        }
        var xrm = _getXrm();
        if (!xrm || !xrm.WebApi) {
            _renderEmpty('Xrm context unavailable.');
            return;
        }
        var options =
            '?$select=new_name,new_abbreviation,new_color,new_sublabel,new_source' +
            '&$filter=_new_contactid_value eq ' + contactId +
            '&$orderby=new_name asc';

        xrm.WebApi.retrieveMultipleRecords('new_contacttag', options).then(
            function (result) {
                _render(result.entities || []);
            },
            function (err) {
                console.error('[ContactTag] query failed', err);
                _renderEmpty('Failed to load tags.');
            }
        );
    }

    function _rowHtml(t) {
        var name = t.new_name || '(untagged)';
        var abbrev = t.new_abbreviation || '';
        var color = _colorFor(t.new_color);
        var sub = t.new_sublabel || '';
        var source = t.new_source || '';
        var textColor = t.new_color === 100000002 ? '#7a6a00' : '#ffffff'; // yellow circle -> dark text

        var subLine = sub || source
            ? '<div class="contact-tag-sub">' + _escape(sub) + '</div>' +
              (source ? '<div class="contact-tag-source">' + _escape(source) + '</div>' : '')
            : '';

        return (
            '<div class="contact-tag-row" data-tid="' + _escape(t.new_contacttagid || '') + '">' +
            '<div class="contact-tag-avatar" style="background:' + color + ';color:' + textColor + '">' +
            _escape(_initials(name, abbrev)) + '</div>' +
            '<div class="contact-tag-body">' +
            '<div class="contact-tag-name">' + _escape(name) + '</div>' +
            subLine +
            '</div>' +
            '<div class="contact-tag-row-menu" title="More">&#8942;</div>' +
            '</div>'
        );
    }

    function _wireClicks() {
        var rows = tagList.querySelectorAll('.contact-tag-row[data-tid]');
        for (var i = 0; i < rows.length; i++) {
            rows[i].addEventListener('click', _onRowClick);
        }
    }

    function _onRowClick(e) {
        // Ignore clicks on the ⋮ menu affordance.
        if (e.target.classList.contains('contact-tag-row-menu')) return;
        var tid = e.currentTarget.getAttribute('data-tid');
        if (!tid) return;
        var xrm = _getXrm();
        // Open the Contact Tag record so its properties show (Tag/Abbrev/Color/SubLabel/Source).
        if (xrm && xrm.Navigation) {
            xrm.Navigation.openForm({ entityName: 'new_contacttag', entityId: tid });
        }
    }

    function _addTag() {
        if (!contactId) return;
        var xrm = _getXrm();
        // createFromEntity pre-fills new_ContactId (the contact this tag belongs to).
        if (xrm && xrm.Navigation) {
            xrm.Navigation.openForm({
                entityName: 'new_contacttag',
                createFromEntity: { id: contactId, entityType: 'contact' },
            });
        }
    }

    function _render(tags) {
        if (!tags.length) {
            _renderEmpty('No tags attached.');
            return;
        }
        tagList.innerHTML = tags.map(_rowHtml).join('');
        _wireClicks();
        paginationEl.textContent = '1-' + tags.length + ' of ' + tags.length;
    }

    function _renderEmpty(msg) {
        tagList.innerHTML = '<div class="contact-tag-empty">' + _escape(msg) + '</div>';
        paginationEl.textContent = '0 of 0';
    }

    function init() {
        tagList = document.getElementById('tagList');
        paginationEl = document.getElementById('tagPagination');
        addTagBtn = document.getElementById('addTagBtn');
        if (addTagBtn) addTagBtn.addEventListener('click', _addTag);
        loadTags();
    }

    ContactTag.init = init;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window, document);
