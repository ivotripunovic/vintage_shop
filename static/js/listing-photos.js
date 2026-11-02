/*
 * Photos on the listing form (templates/products/product_form.html).
 *
 * Each photo is resized in the browser (long edge 2000px, the server's cap
 * too) and uploaded on its own as soon as it is picked, so no request comes
 * near nginx's 20 MB limit and a validation error on the text never loses
 * photos. On a new listing the uploads are pending until the form is saved
 * (hidden "photos" inputs carry their ids in order); on an existing one they
 * are added, removed and reordered right away. See products/photos.py.
 *
 * Without this script the file input posts the photos with the form.
 */
(function () {
    "use strict";

    var section = document.getElementById("fotografije");
    var form = document.getElementById("product-form");
    if (!section || !form || !window.FormData || !("content" in document.createElement("template"))) {
        return;
    }

    var grid = document.getElementById("photo-grid");
    var input = document.getElementById("photo-input");
    var drop = document.getElementById("photo-drop");
    var countEl = document.getElementById("photo-count");
    var errorEl = document.getElementById("photo-error");
    var template = document.getElementById("photo-item-template");
    var config = section.dataset;
    var productId = config.productId || "";
    var maxPhotos = Number(config.maxPhotos);
    var maxEdge = Number(config.maxEdge);
    var maxBytes = Number(config.maxMb) * 1024 * 1024;
    var csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
    var CONCURRENT = 2;
    var queue = [];
    var active = 0;
    var dragged = null;

    // Photos now go up one by one; the form must not post them again
    input.removeAttribute("form");
    input.classList.add("sr-only");
    Array.prototype.forEach.call(section.querySelectorAll(".js-only"), function (el) {
        el.classList.remove("hidden");
    });

    function items() {
        return Array.prototype.slice.call(grid.children);
    }

    function showError(message) {
        errorEl.textContent = message || "";
        errorEl.classList.toggle("hidden", !message);
    }

    function busy() {
        return active + queue.length > 0;
    }

    function refresh() {
        var list = items();
        list.forEach(function (li, index) {
            li.querySelector(".photo-cover-badge").classList.toggle("hidden", index !== 0);
            li.querySelector("[data-action=cover]").classList.toggle("invisible", index === 0);
            li.querySelector("[data-action=left]").disabled = index === 0;
            li.querySelector("[data-action=right]").disabled = index === list.length - 1;
            li.setAttribute("aria-label", index === 0 ? "Naslovna fotografija" : "Fotografija " + (index + 1));
            // "Cropped to a square in search" only matters for the cover
            var coverTip = li.querySelector(".photo-cover-tip");
            coverTip.classList.toggle("hidden", index !== 0 || !coverTip.textContent);
        });
        countEl.textContent = list.length;
        drop.classList.toggle("hidden", list.length >= maxPhotos);
    }

    function post(url, body, contentType) {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", url);
        xhr.setRequestHeader("X-CSRFToken", csrf);
        xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        if (contentType) xhr.setRequestHeader("Content-Type", contentType);
        xhr.send(body);
        return xhr;
    }

    // One reorder request at a time, always with the latest order: two in
    // flight could reach the server in the wrong order and undo a move
    var orderSending = false;
    var orderChanged = false;

    function saveOrder() {
        // A new listing posts its order with the form (hidden inputs)
        if (!productId) return;
        if (orderSending) {
            orderChanged = true;
            return;
        }
        var ids = items()
            .filter(function (li) { return li.dataset.kind === "image"; })
            .map(function (li) { return Number(li.dataset.id); });
        orderSending = true;
        orderChanged = false;
        var xhr = post(config.reorderUrl, JSON.stringify({ image_ids: ids }), "application/json");
        xhr.onloadend = function () {
            orderSending = false;
            if (orderChanged) saveOrder();
        };
    }

    // --- Resizing ---------------------------------------------------------

    function resize(file) {
        // GIFs may be animated, and HEIC can't be decoded by most browsers:
        // those go up as they are and the server decides
        if (!window.createImageBitmap || !/^image\/(jpeg|png|webp)$/.test(file.type)) {
            return Promise.resolve(file);
        }
        return createImageBitmap(file, { imageOrientation: "from-image" }).then(function (bitmap) {
            var scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
            if (scale === 1 && file.size <= 1.5 * 1024 * 1024) {
                if (bitmap.close) bitmap.close();
                return file;
            }
            var canvas = document.createElement("canvas");
            canvas.width = Math.round(bitmap.width * scale);
            canvas.height = Math.round(bitmap.height * scale);
            var context = canvas.getContext("2d");
            context.fillStyle = "#fff";  // transparent PNGs on white, like the server
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
            if (bitmap.close) bitmap.close();
            return new Promise(function (resolve) {
                canvas.toBlob(function (blob) {
                    resolve(blob && blob.size < file.size ? blob : file);
                }, "image/jpeg", 0.85);
            });
        }).catch(function () {
            return file;  // the server resizes too
        });
    }

    // --- Uploading --------------------------------------------------------

    function addFiles(files) {
        showError("");
        var room = maxPhotos - items().length;
        var list = Array.prototype.filter.call(files, function (file) {
            return /^image\//.test(file.type) || /\.(heic|heif)$/i.test(file.name);
        });
        if (list.length < files.length) {
            showError("Neke izabrane datoteke nisu fotografije i preskočene su.");
        }
        if (list.length > room) {
            showError("Oglas može imati najviše " + maxPhotos + " fotografija; dodato je prvih " + Math.max(room, 0) + ".");
            list = list.slice(0, Math.max(room, 0));
        }
        list.forEach(function (file) {
            var li = template.content.firstElementChild.cloneNode(true);
            li.querySelector(".js-only").classList.remove("hidden");
            li.querySelector("img").src = URL.createObjectURL(file);
            li._file = file;
            grid.appendChild(li);
            queue.push(li);
        });
        refresh();
        pump();
    }

    function pump() {
        while (active < CONCURRENT && queue.length) {
            var li = queue.shift();
            if (!li.isConnected) continue;
            active++;
            upload(li, function () {
                active--;
                pump();
            });
        }
    }

    function setProgress(li, fraction) {
        var bar = li.querySelector(".photo-progress");
        bar.classList.toggle("hidden", fraction === null);
        bar.firstElementChild.style.width = Math.round((fraction || 0) * 100) + "%";
    }

    function fail(li, message) {
        setProgress(li, null);
        li.querySelector(".photo-frame").classList.add("opacity-50");
        var error = li.querySelector(".photo-error");
        error.textContent = message;
        error.classList.remove("hidden");
        li.querySelector("[data-action=retry]").classList.remove("hidden");
        li.dataset.failed = "1";
    }

    function ready(li, photo) {
        setProgress(li, null);
        var img = li.querySelector("img");
        URL.revokeObjectURL(img.src);
        img.src = photo.thumb_url;
        li.dataset.id = photo.id;
        li.dataset.kind = photo.kind;
        li.dataset.removeUrl = photo.remove_url;
        li.id = (photo.kind === "image" ? "image-" : "upload-") + photo.id;
        if (photo.kind === "upload") {
            var hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = "photos";
            hidden.value = photo.id;
            hidden.setAttribute("form", "product-form");
            li.insertBefore(hidden, li.firstChild);
        }
        li.querySelector(".photo-cover-tip").textContent = photo.cover_tip || "";
        var tips = li.querySelector(".photo-tips");
        tips.innerHTML = "";
        photo.tips.forEach(function (text) {
            var item = document.createElement("li");
            item.textContent = text;
            tips.appendChild(item);
        });
        delete li._file;
        refresh();  // shows the cover tip if this photo is first
        // Added at the end on the server; keep any reordering done meanwhile
        saveOrder();
    }

    function upload(li, done) {
        var file = li._file;
        setProgress(li, 0);
        resize(file).then(function (blob) {
            if (!li.isConnected) return done();
            if (blob.size > maxBytes) {
                fail(li, "Fotografija je veća od " + config.maxMb + " MB.");
                return done();
            }
            var name = blob === file ? file.name : file.name.replace(/\.[^.]*$/, "") + ".jpg";
            var data = new FormData();
            data.append("photo", blob, name);
            if (productId) data.append("product", productId);

            var xhr = new XMLHttpRequest();
            xhr.open("POST", config.uploadUrl);
            xhr.setRequestHeader("X-CSRFToken", csrf);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.upload.onprogress = function (event) {
                if (event.lengthComputable) setProgress(li, event.loaded / event.total);
            };
            xhr.onload = function () {
                var response = null;
                try { response = JSON.parse(xhr.responseText); } catch (e) { /* not JSON */ }
                if (xhr.status === 201 && response && !li.isConnected) {
                    // Removed while uploading: the server already has it
                    post(response.remove_url);
                } else if (xhr.status === 201 && response) {
                    ready(li, response);
                } else if (xhr.status === 413) {
                    fail(li, "Fotografija je prevelika za otpremanje.");
                } else {
                    fail(li, (response && response.error) || "Otpremanje nije uspelo.");
                }
                done();
            };
            xhr.onerror = function () {
                fail(li, "Veza je prekinuta.");
                done();
            };
            xhr.send(data);
        });
    }

    // --- Actions on a photo ----------------------------------------------

    function remove(li) {
        // An upload under way isn't aborted: the server may already have
        // stored it. It finishes, sees the photo is gone and removes it.
        if (li.dataset.id && li.dataset.removeUrl) {
            if (li.dataset.kind === "image" && !window.confirm("Obrisati ovu fotografiju?")) return;
            post(li.dataset.removeUrl);
        }
        var img = li.querySelector("img");
        if (img.src.indexOf("blob:") === 0) URL.revokeObjectURL(img.src);
        var next = li.nextElementSibling || li.previousElementSibling;
        li.remove();
        refresh();
        // Keep keyboard focus nearby instead of losing it to the page top
        (next ? next.querySelector("[data-action=remove]") : input).focus();
    }

    function move(li, where, button) {
        if (where === "cover") grid.insertBefore(li, grid.firstElementChild);
        if (where === "left" && li.previousElementSibling) grid.insertBefore(li, li.previousElementSibling);
        if (where === "right" && li.nextElementSibling) grid.insertBefore(li.nextElementSibling, li);
        refresh();
        saveOrder();
        if (button && !button.disabled && !button.classList.contains("invisible")) button.focus();
        else li.querySelector("[data-action=remove]").focus();
    }

    grid.addEventListener("click", function (event) {
        var button = event.target.closest("button[data-action]");
        if (!button) return;
        var li = button.closest("li.photo-item");
        var action = button.dataset.action;
        if (action === "remove") return remove(li);
        if (action === "retry") {
            li.querySelector(".photo-error").classList.add("hidden");
            li.querySelector(".photo-frame").classList.remove("opacity-50");
            button.classList.add("hidden");
            delete li.dataset.failed;
            queue.push(li);
            return pump();
        }
        move(li, action, button);
    });

    // --- Picking and dropping files ---------------------------------------

    input.addEventListener("change", function () {
        addFiles(input.files);
        input.value = "";
    });

    function isFileDrag(event) {
        return !dragged && event.dataTransfer && Array.prototype.indexOf.call(event.dataTransfer.types, "Files") !== -1;
    }

    section.addEventListener("dragover", function (event) {
        if (!isFileDrag(event)) return;
        event.preventDefault();
        drop.classList.add("border-stone-900", "bg-neutral-50");
    });
    section.addEventListener("dragleave", function (event) {
        if (!section.contains(event.relatedTarget)) drop.classList.remove("border-stone-900", "bg-neutral-50");
    });
    section.addEventListener("drop", function (event) {
        if (!isFileDrag(event)) return;
        event.preventDefault();
        drop.classList.remove("border-stone-900", "bg-neutral-50");
        addFiles(event.dataTransfer.files);
    });

    // --- Drag to reorder (mouse; touch and keyboard use the arrows) -------

    grid.addEventListener("dragstart", function (event) {
        var li = event.target.closest && event.target.closest("li.photo-item");
        if (!li) return;
        dragged = li;
        li.classList.add("opacity-40");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", "");  // Firefox needs data
    });
    grid.addEventListener("dragover", function (event) {
        if (!dragged) return;
        event.preventDefault();
        var target = event.target.closest("li.photo-item");
        if (!target || target === dragged) return;
        var box = target.getBoundingClientRect();
        var after = event.clientX > box.left + box.width / 2;
        grid.insertBefore(dragged, after ? target.nextElementSibling : target);
    });
    grid.addEventListener("drop", function (event) {
        if (dragged) event.preventDefault();
    });
    grid.addEventListener("dragend", function () {
        if (!dragged) return;
        dragged.classList.remove("opacity-40");
        dragged = null;
        refresh();
        saveOrder();
    });
    function makeDraggable() {
        items().forEach(function (li) { li.draggable = true; });
    }
    new MutationObserver(makeDraggable).observe(grid, { childList: true });
    makeDraggable();

    // --- Saving -----------------------------------------------------------

    // Capture phase, so the autosave handler doesn't clear the draft text
    // for a submit that is held back
    form.addEventListener("submit", function (event) {
        if (busy()) {
            event.preventDefault();
            event.stopImmediatePropagation();
            showError("Sačekajte da se fotografije otpreme, pa sačuvajte.");
            section.scrollIntoView({ behavior: "smooth" });
            return;
        }
        // No second submit from a double click. After this tick, so the
        // clicked button's name/value is still sent.
        setTimeout(function () {
            Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (button) {
                button.disabled = true;
            });
        }, 0);
    }, true);

    // Back to this page from the browser cache: the buttons work again
    window.addEventListener("pageshow", function () {
        Array.prototype.forEach.call(form.querySelectorAll("button[type=submit]"), function (button) {
            button.disabled = false;
        });
    });

    window.addEventListener("beforeunload", function (event) {
        if (busy()) {
            event.preventDefault();
            event.returnValue = "";
        }
    });

    refresh();
})();
