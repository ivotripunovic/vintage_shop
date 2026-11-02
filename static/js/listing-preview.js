/*
 * Step bar and live preview on the listing form
 * (templates/products/product_form.html).
 *
 * - Keeps the step bar below the sticky site header, whose height changes.
 * - Shows what each part still needs: photos, required details, tips.
 * - Draws the buyer's search card from the form as the seller types.
 * - Checks the text rules of products/quality.py live; the messages come
 *   from the page, so the wording matches the tips after saving.
 */
(function () {
    "use strict";

    var form = document.getElementById("product-form");
    var steps = document.getElementById("listing-steps");
    var grid = document.getElementById("photo-grid");
    var rulesEl = document.getElementById("listing-tip-rules");
    if (!form || !steps || !grid || !rulesEl) return;

    var rules = JSON.parse(rulesEl.textContent);
    var maxPhotos = (document.getElementById("fotografije") || {}).dataset.maxPhotos;

    // --- Step bar under the sticky header ---------------------------------

    var header = document.querySelector("body > header, header.sticky");
    function placeSteps() {
        var height = header ? header.getBoundingClientRect().height : 0;
        document.documentElement.style.setProperty("--header-height", height + "px");
    }
    if (header && window.ResizeObserver) new ResizeObserver(placeSteps).observe(header);
    placeSteps();

    // --- Reading the form -------------------------------------------------

    function field(name) {
        return form.elements[name];
    }
    function value(name) {
        var el = field(name);
        return el ? String(el.value || "").trim() : "";
    }
    function photos() {
        // Uploaded photos only; one still uploading isn't on the listing yet
        return grid.querySelectorAll("li.photo-item[data-id]");
    }
    function photoHasTips() {
        return Array.prototype.some.call(photos(), function (li) {
            var cover = li.querySelector(".photo-cover-tip");
            return li.querySelector(".photo-tips li") || (cover && !cover.classList.contains("hidden"));
        });
    }

    var REQUIRED = [
        ["title", "naziv"],
        ["description", "opis"],
        ["price", "cena"],
        ["category", "kategorija"],
        ["condition", "stanje"],
    ];

    // --- The text rules from products/quality.py --------------------------

    // Count like Python's len(): characters, not UTF-16 units (emoji)
    function chars(text) {
        return Array.from(text).length;
    }

    function textFailures(title, rawDescription) {
        var failed = [];
        // The browser submits line breaks as CRLF and the server keeps them
        var description = rawDescription.replace(/\r?\n/g, "\r\n");
        var words = title.split(/\s+/).filter(Boolean);
        if (chars(title) < rules.min_title_chars || words.length < rules.min_title_words) {
            failed.push("title");
        }
        var letters = title.match(/\p{L}/gu) || [];
        var shouting = letters.every(function (c) {
            return c === c.toUpperCase() && c !== c.toLowerCase();
        });
        if (letters.length >= rules.min_capitals && shouting) failed.push("capitals");
        if (chars(description) < rules.min_description_chars) failed.push("description");
        // Python's \d matches any decimal digit, not only 0-9
        if (!/\p{Nd}/u.test(description)) failed.push("measurements");
        return failed;
    }

    // --- Drawing ----------------------------------------------------------

    function setStatus(step, text, done) {
        var el = steps.querySelector('[data-step-status="' + step + '"]');
        el.textContent = text;
        el.classList.toggle("text-emerald-700", !!done);
        el.classList.toggle("text-stone-400", !done);
    }

    // Same as PRICE_PATTERN in products/forms.py: whole dinars, optionally
    // grouped (4.500, 4 500), with zero decimals allowed (4500,00). Anything
    // the server would reject shows no price.
    var PRICE = /^(\d+|\d{1,3}(?:[. ]\d{3})+)(?:[.,]0{1,2})?$/;

    function formatPrice(raw) {
        var match = PRICE.exec(raw);
        if (!match) return "";
        var whole = Number(match[1].replace(/[. ]/g, ""));
        return whole > 0 ? whole.toLocaleString("de-DE") + " RSD" : "";
    }

    function categoryName() {
        var select = field("category");
        if (!select || !select.value) return "";
        var text = select.options[select.selectedIndex].text;
        // Subcategories read "Parent › Child"; the card shows the child
        return text.split("›").pop().trim();
    }

    function update() {
        var photoList = photos();
        var count = photoList.length;

        // 1 · Photos
        setStatus("photos", count ? "✓ " + count + " / " + maxPhotos : "nedostaje", count > 0);

        // 2 · Details
        var missing = REQUIRED.filter(function (pair) { return !value(pair[0]); })
            .map(function (pair) { return pair[1]; });
        setStatus("details", missing.length ? "nedostaje: " + missing.join(", ") : "✓ popunjeno", !missing.length);

        // 3 · Preview: the card
        var cover = photoList[0] && photoList[0].querySelector("img");
        var image = document.getElementById("preview-image");
        if (cover && cover.src) image.src = cover.src;
        image.classList.toggle("hidden", !cover);
        document.getElementById("preview-no-image").classList.toggle("hidden", !!cover);
        document.getElementById("preview-title").textContent = value("title") || "Naziv proizvoda";
        document.getElementById("preview-price").textContent = formatPrice(value("price"));
        document.getElementById("preview-category").textContent = categoryName();

        // 3 · Preview: the tips
        var shown = textFailures(value("title"), value("description"));
        var countTip = document.querySelector('#preview-tips [data-tip="count"]');
        if (count < rules.min_photos) {
            countTip.textContent = count ? countTip.dataset.few : countTip.dataset.none;
            shown.push("count");
        }
        if (photoHasTips()) shown.push("photos");
        Array.prototype.forEach.call(document.querySelectorAll("#preview-tips [data-tip]"), function (li) {
            li.classList.toggle("hidden", shown.indexOf(li.dataset.tip) === -1);
        });
        document.getElementById("preview-ok").classList.toggle("hidden", shown.length > 0);
        setStatus("preview", shown.length ? shown.length + (shown.length === 1 ? " savet" : " saveta") : "✓ spremno", !shown.length);

        var needsPhoto = document.getElementById("publish-needs-photo");
        if (needsPhoto) needsPhoto.classList.toggle("hidden", count > 0);
    }

    var pending;
    function soon() {
        clearTimeout(pending);
        pending = setTimeout(update, 150);
    }
    form.addEventListener("input", soon);
    form.addEventListener("change", soon);
    // Photos added, removed, reordered or finished uploading (data-id set,
    // tips filled in) all change the grid
    new MutationObserver(soon).observe(grid, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-id", "class"],
    });
    update();
})();
