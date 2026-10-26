import json
import os
import re
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import websocket
import threading
import time
import subprocess
import queue as _queue


# ============================================================
# НАСТРОЙКИ
# ============================================================

PORT = 9222

GITHUB_URL = "https://github.com/Dartrongus/DwarTools"
USEFUL_LINKS_URL = "https://dartrongus.github.io/dwar/menu"

ACCENT_COLOR = "#7c9cff"


# ============================================================
# JAVASCRIPT DWARTOOLS
# ============================================================

JS_CODE = r"""
(async function () {
    'use strict';

    const CONTAINER_ID = 'dwar-artifacts-list-bookmarklet';
    const TOOLTIP_CLASS = 'dwar-artifact-tooltip-bookmarklet';
    const CARD_CLASS = 'dwar-artifact-card-bookmarklet';
    const EMB_TOOLTIP_CLASS = 'dwar-artifact-embedded-tooltip-bookmarklet';
    const INFO_PANEL_ID = 'dwar-tools-info-panel';

    const server = location.hostname.split('.')[0];
    const baseUrl = `https://${server}.dwar.ru`;

    const tooltipCache = new Map();
    const cache = new Map();

    let activeTooltip = null;
    let hoverRequestId = 0;
    let activeEmbTooltip = null;

    document.getElementById(CONTAINER_ID)?.remove();

    document.querySelectorAll(`.${TOOLTIP_CLASS}`).forEach(element => {
        element.remove();
    });

    document.querySelectorAll(`.${EMB_TOOLTIP_CLASS}`).forEach(element => {
        element.remove();
    });

    document.getElementById(INFO_PANEL_ID)?.remove();


    function getNickname() {
        try {
            const params = new URLSearchParams(location.search);
            const nick = params.get('nick');

            if (nick) {
                return nick;
            }
        } catch (error) {
            console.warn('[DwarTools] Ошибка чтения nick:', error);
        }

        return null;
    }


    function getGameInfoLink() {
        const buttons = Array.from(
            document.querySelectorAll(
                'input[type="button"], input[type="submit"], button'
            )
        );

        for (const element of buttons) {
            const value = (
                element.value ||
                element.textContent ||
                ''
            ).trim();

            if (value !== 'Перейти к игровой информации') {
                continue;
            }

            const onclick = element.getAttribute('onclick') || '';

            const match = onclick.match(
                /location\.href\s*=\s*['"]([^'"]+)['"]/i
            );

            if (match && match[1]) {
                const url = match[1].replace(/&amp;/gi, '&');

                try {
                    return new URL(url, location.href).href;
                } catch (error) {
                    return url;
                }
            }
        }

        return null;
    }


    function hasArtifactData() {
        return Array.from(
            document.querySelectorAll('script:not([src])')
        ).some(script => {
            return (
                script.textContent &&
                /art_alt\s*\[\s*["'][^"']+["']\s*\]\s*=/.test(
                    script.textContent
                )
            );
        });
    }


    function detectPageType() {
        const path = location.pathname.toLowerCase();

        const nickname = getNickname();
        const gameInfoLink = getGameInfoLink();
        const artifactData = hasArtifactData();

        const isCharacterPath =
            path.includes('user_info') ||
            path.includes('character') ||
            path.includes('pers_info') ||
            path.includes('player');

        const isNonCharacterPath =
            path.includes('artifact_info') ||
            path.includes('effect_info') ||
            path.includes('companion_info');


        if (gameInfoLink) {
            return {
                type: 'appearance',
                nickname,
                gameInfoLink
            };
        }


        if (isCharacterPath && nickname) {
            return {
                type: 'game',
                nickname,
                gameInfoLink: null
            };
        }


        if (isCharacterPath && artifactData) {
            return {
                type: 'game',
                nickname,
                gameInfoLink: null
            };
        }


        if (nickname && !isNonCharacterPath) {
            return {
                type: 'game',
                nickname,
                gameInfoLink: null
            };
        }


        return {
            type: 'other',
            nickname,
            gameInfoLink: null
        };
    }


    function hideAllTooltips() {
        document.querySelectorAll(
            `.${TOOLTIP_CLASS}`
        ).forEach(tooltip => {
            tooltip.style.display = 'none';
        });

        document.querySelectorAll(
            `.${EMB_TOOLTIP_CLASS}`
        ).forEach(tooltip => {
            tooltip.style.display = 'none';
        });

        activeTooltip = null;
        activeEmbTooltip = null;
        hoverRequestId++;
    }

    function positionTooltip(tooltipEl, event, width, height) {
        let x = event.clientX + 15;
        let y = event.clientY + 15;

        if (x + width > window.innerWidth) {
            x = event.clientX - width;
        }

        if (y + height > window.innerHeight) {
            y = window.innerHeight - height - 10;
        }

        if (x < 10) {
            x = 10;
        }

        if (y < 10) {
            y = 10;
        }

        tooltipEl.style.left = `${x}px`;
        tooltipEl.style.top = `${y}px`;
    }


    async function loadTooltip(url) {
        if (tooltipCache.has(url)) {
            return tooltipCache.get(url);
        }

        try {
            const response = await fetch(url, {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const html = await response.text();

            const parsedDocument = new DOMParser().parseFromString(
                html,
                'text/html'
            );

            const tooltipContent =
                parsedDocument.querySelector('.bg-inner-b')?.innerHTML || '';

            tooltipCache.set(url, tooltipContent);

            return tooltipContent;

        } catch (error) {
            console.warn(
                '[DwarTools] Не удалось загрузить описание:',
                url,
                error
            );

            return `
                <div style="padding:10px;">
                    Не удалось загрузить описание предмета
                </div>
            `;
        }
    }


    // ============================================================
    // НОВАЯ ЛОГИКА: вложения (руны, оправы, узоры, символы, etc.)
    // ============================================================

    function makeBadge(text) {
        const badge = document.createElement('span');
        badge.textContent = text;
        badge.style.cssText =
            'color:#7a4a00;font-weight:700;font-size:9px;' +
            'background:rgba(122,74,0,.18);padding:1px 5px;' +
            'border-radius:3px;flex-shrink:0;line-height:1.4;' +
            'align-self:flex-start;margin-top:1px';
        return badge;
    }


    function makeIcon(data, size) {
        size = size || 16;

        const icon = document.createElement('img');

        if (data.picture) {
            icon.src = baseUrl + String(data.picture).replace(/\\/g, '');
        }

        icon.alt = '';
        icon.style.cssText =
            `width:${size}px;height:${size}px;` +
            'object-fit:contain;flex-shrink:0;margin-top:1px';

        icon.addEventListener('error', () => icon.remove());

        return icon;
    }


    function makeTitle(emb, clamp) {
        const color = emb.data.color || '#333';

        const title = document.createElement('span');

        const baseStyle =
            `color:${color};font-weight:600;flex:1;` +
            'word-break:break-word;line-height:1.25';

        title.style.cssText = clamp && clamp > 0
            ? `${baseStyle};overflow:hidden;display:-webkit-box;` +
              `-webkit-line-clamp:${clamp};-webkit-box-orient:vertical`
            : baseStyle;

        let text = emb.data.title || 'Без названия';

        if (emb.sharpening) {
            text += ' ' + emb.sharpening;
        }

        title.textContent = text;

        return title;
    }


    function buildEmbTooltipHtml(emb) {
        const data = emb.data;
        const sharpening = emb.sharpening;
        const color = data.color || '#333';

        const html = [];

        html.push(
            `<div style="font-weight:700;color:${color};` +
            `margin-bottom:6px;font-size:13px">` +
            `${data.title || 'Без названия'}` +
            (sharpening
                ? ` <span style="color:#0a0;font-weight:700">` +
                  `${sharpening}</span>`
                : '') +
            `</div>`
        );

        if (data.lev && data.lev.value) {
            html.push(
                `<div style="color:#555;margin-bottom:4px">` +
                `Уровень: ${data.lev.value}</div>`
            );
        }

        if (data.trend) {
            html.push(
                `<div style="color:#555;margin-bottom:4px">` +
                `Направление: ${data.trend}</div>`
            );
        }

        if (data.skills && data.skills.length) {
            html.push(
                '<div style="margin-top:6px;font-weight:600;' +
                'color:#333;margin-bottom:3px">Характеристики:</div>'
            );

            html.push('<div style="padding-left:6px">');

            data.skills.forEach(skill => {
                const value = String(skill.value || '')
                    .replace(/<[^>]*>/g, '')
                    .trim();

                html.push(
                    `<div style="color:${color}">` +
                    `${skill.title}: ${value}</div>`
                );
            });

            html.push('</div>');
        }

        if (data.desc) {
            let cleanDesc = String(data.desc)
                .replace(/<[^>]*>/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();

            if (cleanDesc.length > 400) {
                cleanDesc = cleanDesc.slice(0, 400) + '…';
            }

            html.push(
                `<div style="margin-top:6px;color:#555;` +
                `font-style:italic">${cleanDesc}</div>`
            );
        }

        return html.join('');
    }


    function attachEmbHover(element, emb) {
        element.style.cursor = 'help';

        element.addEventListener('mouseenter', event => {
            hideAllTooltips();

            const tooltip = (function () {
                let tooltip = document.querySelector(
                    `.${EMB_TOOLTIP_CLASS}`
                );

                if (!tooltip) {
                    tooltip = document.createElement('div');
                    tooltip.className = EMB_TOOLTIP_CLASS;
                    tooltip.style.cssText =
                        'position:fixed;padding:10px;' +
                        'box-shadow:0 2px 8px rgba(0,0,0,.35);' +
                        'display:none;z-index:2147483647;' +
                        'width:340px;' +
                        'max-width:calc(100vw - 20px);' +
                        'border-radius:4px;background:#fff8e7;' +
                        'pointer-events:none;box-sizing:border-box;' +
                        'font-size:12px;line-height:1.4;color:#333';
                    document.body.appendChild(tooltip);
                }

                return tooltip;
            })();

            activeEmbTooltip = tooltip;

            positionTooltip(tooltip, event, 360, 340);

            tooltip.innerHTML = buildEmbTooltipHtml(emb);
            tooltip.style.display = 'block';

            element.style.background = 'rgba(122,74,0,.12)';
        });

        element.addEventListener('mousemove', event => {
            if (activeEmbTooltip) {
                positionTooltip(activeEmbTooltip, event, 360, 340);
            }
        });

        element.addEventListener('mouseleave', () => {
            if (activeEmbTooltip) {
                activeEmbTooltip.style.display = 'none';
                activeEmbTooltip = null;
            }

            element.style.background = 'transparent';
        });
    }


    function detectEmbeddedLabel(tdLabel, linkText, data) {
        if (tdLabel === 'Руна') return 'Руна';
        if (tdLabel === 'Оправа') return 'Оправа';
        if (tdLabel === 'Узор') return 'Узор';
        if (tdLabel === 'Магический символ') return 'Магический символ';
        if (tdLabel === 'Драгоценный камень') return 'Драгоценный камень';
        if (tdLabel === 'Пластина') return 'Пластина';
        if (tdLabel === 'Заточено') return 'Заточка';

        const text = (linkText || data.title || '').toLowerCase();

        if (text.includes('символ')) return 'Магический символ';
        if (text.includes('оправа')) return 'Оправа';
        if (text.includes('узор')) return 'Узор';
        if (text.includes('руна')) return 'Руна';
        if (text.includes('пластина')) return 'Пластина';

        const typeId = parseInt(data.type_id, 10);

        if (typeId === 230) return 'Узор';
        if (typeId === 117) return 'Оправа';
        if (typeId === 29) return 'Руна';

        if (typeId === 179 || data.kind === 'Магический символ') {
            return 'Магический символ';
        }

        return null;
    }


    async function loadArtifactInfo(url) {
        if (cache.has(url)) {
            return cache.get(url);
        }

        const promise = (async () => {
            try {
                const response = await fetch(url, {
                    credentials: 'same-origin'
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const html = await response.text();

                const doc = new DOMParser().parseFromString(
                    html,
                    'text/html'
                );

                const tip =
                    doc.querySelector('.bg-inner-b')?.innerHTML || '';

                const altMap = new Map();

                doc.querySelectorAll('script:not([src])').forEach(script => {
                    const matches = [...script.textContent.matchAll(
                        /art_alt\["([^"]+)"\]\s*=\s*(\{[\s\S]*?\});/g
                    )];

                    for (const [, divId, body] of matches) {
                        try {
                            const data = Function(
                                `"use strict";return(${body});`
                            )();

                            if (data && typeof data === 'object') {
                                altMap.set(divId, data);
                            }
                        } catch (e) {
                            console.warn(
                                '[DwarTools] art_alt parse error:',
                                e
                            );
                        }
                    }
                });

                const embedded = [];
                const seenIds = new Set();
                let lastWasSymbol = false;

                doc.querySelectorAll('a[div_id]').forEach(link => {
                    const divId = link.getAttribute('div_id');

                    if (!divId || !altMap.has(divId) || seenIds.has(divId)) {
                        return;
                    }

                    const row = link.closest('tr');

                    if (!row) {
                        return;
                    }

                    const cells = row.querySelectorAll('td');

                    if (cells.length < 2) {
                        return;
                    }

                    const tdLabel = cells[0].textContent
                        .replace(/\u00A0/g, '')
                        .trim();

                    const linkText = link.textContent || '';
                    const data = altMap.get(divId);

                    let label = detectEmbeddedLabel(
                        tdLabel,
                        linkText,
                        data
                    );

                    if (!label && tdLabel === '' && lastWasSymbol) {
                        label = 'Магический символ';
                    }

                    if (!label) {
                        return;
                    }

                    lastWasSymbol = label === 'Магический символ';

                    let sharpening = null;

                    const sharpeningMatch = linkText.match(
                        /(\(▲\d+%\))/
                    );

                    if (sharpeningMatch) {
                        sharpening = sharpeningMatch[1];
                    }

                    seenIds.add(divId);

                    embedded.push({
                        label,
                        data,
                        sharpening
                    });
                });

                return { tip, emb: embedded };

            } catch (error) {
                console.warn(
                    '[DwarTools] load failed:',
                    url,
                    error
                );

                return {
                    tip: '<div style="padding:10px;">' +
                         'Не удалось загрузить описание предмета' +
                         '</div>',
                    emb: []
                };
            }
        })();

        cache.set(url, promise);

        return promise;
    }


    function buildEnchantOverlay(emb) {
        if (!emb || emb.length === 0) {
            return null;
        }

        const rune = emb.find(e => e.label === 'Руна');
        const oprava = emb.find(e => e.label === 'Оправа');

        if (!rune && !oprava) {
            return null;
        }

        const overlay = document.createElement('span');
        overlay.className = 'enchants';
        overlay.style.cssText =
            'position:absolute;top:2px;left:2px;' +
            'display:flex;flex-direction:column;gap:2px;' +
            'z-index:2;pointer-events:none';

        if (oprava) {
            const img = document.createElement('img');
            img.src = `${baseUrl}/images/enchants/oprava.png`;
            img.alt = '';
            img.className = 'enchant2_png';
            img.style.cssText = 'width:18px;height:18px;display:block';
            img.addEventListener('error', () => img.remove());
            overlay.appendChild(img);
        }

        if (rune) {
            const quality = parseInt(rune.data.quality, 10) || 1;

            const img = document.createElement('img');
            img.src = `${baseUrl}/images/enchants/1_${quality}.png`;
            img.alt = '';
            img.className = 'enchant_png';
            img.style.cssText = 'width:18px;height:18px;display:block';
            img.addEventListener('error', () => img.remove());
            overlay.appendChild(img);
        }

        return overlay;
    }


    function renderEmbeddedList(emb, container) {
        const groupOrder = [];
        const groups = new Map();

        emb.forEach(item => {
            if (!groups.has(item.label)) {
                groups.set(item.label, []);
                groupOrder.push(item.label);
            }

            groups.get(item.label).push(item);
        });

        groupOrder.forEach(label => {
            const items = groups.get(label);

            if (items.length === 1) {
                const row = document.createElement('div');
                row.className = 'dwar-artifact-embedded-row-bookmarklet';
                row.style.cssText =
                    'display:flex;align-items:flex-start;gap:4px;' +
                    'padding:3px 4px;border-radius:4px;' +
                    'font-size:10px;line-height:1.3';

                row.append(
                    makeBadge(items[0].label),
                    makeIcon(items[0].data),
                    makeTitle(items[0], 0)
                );

                attachEmbHover(row, items[0]);

                container.appendChild(row);
            } else {
                const group = document.createElement('div');
                group.style.cssText = 'padding:3px 4px;border-radius:4px';

                const header = document.createElement('div');
                header.style.cssText =
                    'display:flex;align-items:center;gap:4px;' +
                    'margin-bottom:2px';

                header.appendChild(
                    makeBadge(`${label} (${items.length})`)
                );

                group.appendChild(header);

                items.forEach(emb => {
                    const sub = document.createElement('div');
                    sub.style.cssText =
                        'display:flex;align-items:flex-start;gap:4px;' +
                        'padding:2px 4px 2px 14px;border-radius:3px;' +
                        'font-size:10px;line-height:1.3';

                    sub.append(
                        makeIcon(emb.data),
                        makeTitle(emb, 0)
                    );

                    attachEmbHover(sub, emb);

                    group.appendChild(sub);
                });

                container.appendChild(group);
            }
        });
    }


    function renderCard({ data, level }) {
        if (!data) {
            return null;
        }

        const artifactId = data.id;

        if (!artifactId) {
            console.warn('[DwarTools] missing id:', data);
            return null;
        }

        const artifactUrl =
            `${baseUrl}/artifact_info.php?artifact_id=${artifactId}`;

        const card = document.createElement('div');
        card.className = CARD_CLASS;

        const border = (function (color) {
            if (!color) {
                return null;
            }

            const c = color.toLowerCase();

            if (c === '#f400a1') return '2px solid #f400a1';
            if (c === '#f55e27') return '2px solid #f55e27';

            return null;
        })(data.color);

        card.style.cssText =
            `width:260px;min-height:130px;` +
            'display:flex;flex-direction:column;' +
            `border:${border || '1px solid #e0e0e0'};` +
            'padding:10px;border-radius:8px;' +
            'background:#ffe2a8;box-sizing:border-box;' +
            'position:relative;' +
            'transition:box-shadow .2s,transform .2s';

        card.addEventListener('mouseenter', () => {
            card.style.boxShadow = '0 4px 10px rgba(0,0,0,.25)';
            card.style.transform = 'translateY(-2px)';
        });

        card.addEventListener('mouseleave', () => {
            card.style.boxShadow = 'none';
            card.style.transform = 'none';
        });

        const link = document.createElement('a');
        link.href = artifactUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.style.cssText =
            'text-decoration:none;display:flex;' +
            'flex-direction:column;align-items:flex-start;' +
            'gap:6px;width:100%;min-height:110px;' +
            'position:relative';

        const topRow = document.createElement('div');
        topRow.style.cssText =
            'display:flex;align-items:flex-start;gap:10px;' +
            'width:100%';

        const imageWrap = document.createElement('div');
        imageWrap.style.cssText =
            'position:relative;width:80px;' +
            'max-height:100px;flex-shrink:0';

        const image = document.createElement('img');

        if (data.picture) {
            image.src = `${baseUrl}` +
                `${String(data.picture).replace(/\\/g, '')}`;
        }

        image.alt = data.title || 'Предмет';
        image.style.cssText =
            'width:80px;max-height:100px;object-fit:contain;' +
            'flex-shrink:0';

        image.addEventListener('error', () => {
            image.style.display = 'none';
        });

        imageWrap.appendChild(image);

        const title = document.createElement('span');
        title.textContent = data.title || 'Без названия';
        title.style.cssText =
            `color:${data.color || '#000'};` +
            'font-weight:700;line-height:1.25;' +
            'display:-webkit-box;-webkit-line-clamp:3;' +
            '-webkit-box-orient:vertical;overflow:hidden;' +
            'word-break:break-word';

        topRow.append(imageWrap, title);
        link.appendChild(topRow);

        const copyLink = document.createElement('a');
        copyLink.href = '#';
        copyLink.textContent = 'скопировать ссылку';
        copyLink.title = 'Копировать ссылку на предмет';
        copyLink.style.cssText =
            'font-size:10px;color:#7a4a00;' +
            'text-decoration:underline;cursor:pointer;' +
            'align-self:flex-start;padding:0;margin-top:2px;' +
            'opacity:.85';

        copyLink.addEventListener('mouseenter', () => {
            copyLink.style.opacity = '1';
        });

        copyLink.addEventListener('mouseleave', () => {
            copyLink.style.opacity = '.85';
        });

        copyLink.addEventListener('click', async event => {
            event.preventDefault();
            event.stopPropagation();

            try {
                await navigator.clipboard.writeText(artifactUrl);
            } catch (err) {
                const textArea = document.createElement('textarea');
                textArea.value = artifactUrl;
                textArea.style.position = 'fixed';
                textArea.style.opacity = '0';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {
                    document.execCommand('copy');
                } finally {
                    textArea.remove();
                }
            }

            const oldText = copyLink.textContent;
            copyLink.textContent = '✓ скопировано';

            setTimeout(() => {
                copyLink.textContent = oldText;
            }, 1000);
        });

        link.appendChild(copyLink);

        const embWrap = document.createElement('div');
        embWrap.style.cssText =
            'margin-top:8px;' +
            'border-top:1px dashed rgba(122,74,0,.3);' +
            'padding-top:6px;display:flex;' +
            'flex-direction:column;gap:2px';

        const embLoading = document.createElement('div');
        embLoading.textContent = 'Загрузка вложений…';
        embLoading.style.cssText =
            'font-size:10px;color:#7a4a00;font-style:italic;' +
            'padding:2px 0';

        embWrap.appendChild(embLoading);

        loadArtifactInfo(artifactUrl).then(({ emb }) => {
            const overlay = buildEnchantOverlay(emb);

            if (overlay) {
                imageWrap.appendChild(overlay);
            }

            embWrap.innerHTML = '';

            if (!emb || emb.length === 0) {
                const empty = document.createElement('div');
                empty.textContent = 'Без вложений';
                empty.style.cssText =
                    'font-size:10px;color:#999;font-style:italic;' +
                    'padding:2px 0';
                embWrap.appendChild(empty);
                return;
            }

            renderEmbeddedList(emb, embWrap);
        }).catch(() => {
            embWrap.innerHTML = '';

            const error = document.createElement('div');
            error.textContent = 'Ошибка загрузки вложений';
            error.style.cssText =
                'font-size:10px;color:#c00;font-style:italic';
            embWrap.appendChild(error);
        });

        card.appendChild(link);
        card.appendChild(embWrap);

        return card;
    }


    function renderCards(container, items) {
        items.forEach(item => {
            const card = renderCard(item);

            if (card) {
                container.appendChild(card);
            }
        });
    }


    function extractObjectsFromScript(text) {
        const artifacts = [];

        const assignmentRegex =
            /art_alt\s*\[\s*["'][^"']+["']\s*\]\s*=/g;

        let match;


        while ((match = assignmentRegex.exec(text)) !== null) {
            let position = assignmentRegex.lastIndex;


            while (
                position < text.length &&
                /\s/.test(text[position])
            ) {
                position++;
            }


            if (text[position] !== '{') {
                continue;
            }


            const start = position;

            let depth = 0;
            let inString = false;
            let stringQuote = '';
            let escaped = false;


            for (; position < text.length; position++) {
                const char = text[position];


                if (inString) {
                    if (escaped) {
                        escaped = false;
                        continue;
                    }


                    if (char === '\\') {
                        escaped = true;
                        continue;
                    }


                    if (char === stringQuote) {
                        inString = false;
                    }

                    continue;
                }


                if (char === '"' || char === "'") {
                    inString = true;
                    stringQuote = char;
                    continue;
                }


                if (char === '{') {
                    depth++;

                } else if (char === '}') {
                    depth--;

                    if (depth === 0) {
                        break;
                    }
                }
            }


            if (depth !== 0) {
                continue;
            }


            const objectText = text.slice(
                start,
                position + 1
            );


            try {
                const artifact = Function(
                    `"use strict"; return (${objectText});`
                )();


                if (
                    artifact &&
                    typeof artifact === 'object'
                ) {
                    artifacts.push(artifact);
                }

            } catch (error) {
                console.warn(
                    '[DwarTools] Ошибка разбора объекта:',
                    error
                );
            }


            assignmentRegex.lastIndex = position + 1;
        }


        return artifacts;
    }


    function findArtifacts() {
        const artifacts = [];


        document.querySelectorAll(
            'script:not([src])'
        ).forEach(script => {

            if (!script.textContent) {
                return;
            }


            const objects = extractObjectsFromScript(
                script.textContent
            );


            objects.forEach(artifact => {
                const level = parseInt(
                    artifact.lev?.value ?? 0,
                    10
                ) || 0;


                const kind = artifact.kind || '';


                const isAccessory =
                    kind === 'Кольца' ||
                    kind === 'Амулет';


                if (
                    artifact.dur_max ||
                    kind === 'Знамена'
                ) {
                    artifacts.push({
                        data: artifact,
                        level,
                        isAccessory
                    });
                }
            });
        });


        const uniqueArtifacts = [];
        const seenArtifacts = new Set();


        for (const artifact of artifacts) {
            const id = artifact.data?.id;


            const uniqueKey = id
                ? `id:${id}`
                : `title:${artifact.data?.title || ''}`;


            if (!seenArtifacts.has(uniqueKey)) {
                seenArtifacts.add(uniqueKey);
                uniqueArtifacts.push(artifact);
            }
        }


        uniqueArtifacts.sort((a, b) => {
            if (a.isAccessory !== b.isAccessory) {
                return Number(a.isAccessory) -
                       Number(b.isAccessory);
            }

            return b.level - a.level;
        });


        return uniqueArtifacts;
    }


    function createDwarToolsPanel(pageInfo, artifacts) {

        document.getElementById(
            INFO_PANEL_ID
        )?.remove();


        const panel = document.createElement('div');

        panel.id = INFO_PANEL_ID;


        panel.style.cssText = `
            position: fixed;
            right: 18px;
            bottom: 18px;
            width: 330px;
            max-width: calc(100vw - 36px);
            padding: 15px;
            z-index: 2147483646;
            background: rgba(18, 21, 28, .98);
            color: #fff;
            border: 1px solid rgba(255,255,255,.12);
            border-radius: 12px;
            box-shadow: 0 14px 45px rgba(0,0,0,.45);
            font-family: Segoe UI, Arial, sans-serif;
            box-sizing: border-box;
        `;


        const header = document.createElement('div');

        header.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 11px;
        `;


        const title = document.createElement('div');

        title.textContent = '⚔ DwarTools';

        title.style.cssText = `
            font-size: 17px;
            font-weight: 700;
        `;

        header.appendChild(title);


        const serverLabel = document.createElement('div');

        serverLabel.textContent =
            server.toUpperCase();

        serverLabel.style.cssText = `
            color: #7c9cff;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 6px;
            background: rgba(124,156,255,.12);
        `;

        header.appendChild(serverLabel);

        panel.appendChild(header);


        if (pageInfo.nickname) {
            const nick = document.createElement('div');

            nick.textContent =
                `Персонаж: ${pageInfo.nickname}`;

            nick.style.cssText = `
                color: #cfd5df;
                font-size: 13px;
                margin-bottom: 12px;
                word-break: break-word;
            `;

            panel.appendChild(nick);
        }


        const buttons = document.createElement('div');

        buttons.style.cssText = `
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 7px;
        `;


        function makeButton(
            text,
            callback,
            fullWidth = false
        ) {
            const button =
                document.createElement('button');


            button.type = 'button';
            button.textContent = text;


            button.style.cssText = `
                width: 100%;
                min-height: 36px;
                padding: 8px 10px;
                border: 1px solid rgba(255,255,255,.08);
                border-radius: 7px;
                background: #2a303b;
                color: #fff;
                cursor: pointer;
                font-size: 12px;
                font-weight: 600;
                text-align: center;
                transition: background .15s, border-color .15s;
                box-sizing: border-box;
                ${fullWidth ? 'grid-column: 1 / -1;' : ''}
            `;


            button.addEventListener(
                'mouseenter',
                () => {
                    button.style.background =
                        '#394251';

                    button.style.borderColor =
                        'rgba(124,156,255,.35)';
                }
            );


            button.addEventListener(
                'mouseleave',
                () => {
                    button.style.background =
                        '#2a303b';

                    button.style.borderColor =
                        'rgba(255,255,255,.08)';
                }
            );


            button.addEventListener(
                'click',
                callback
            );


            return button;
        }


        if (pageInfo.nickname) {
            const encodedNick =
                encodeURIComponent(
                    pageInfo.nickname
                );


            const shadowUrl =
                `${baseUrl}/companion_info.php?nick=${encodedNick}`;


            const effectsUrl =
                `${baseUrl}/effect_info.php?nick=${encodedNick}`;


            buttons.appendChild(
                makeButton(
                    '👻  Тень',
                    () => {
                        window.open(
                            shadowUrl,
                            '_blank'
                        );
                    }
                )
            );


            buttons.appendChild(
                makeButton(
                    '✨  Эффекты',
                    () => {
                        window.open(
                            effectsUrl,
                            '_blank'
                        );
                    }
                )
            );
        }


        if (
            pageInfo.type === 'appearance' &&
            pageInfo.gameInfoLink
        ) {
            buttons.appendChild(
                makeButton(
                    '🎭  Игровая информация',
                    () => {
                        window.open(
                            pageInfo.gameInfoLink,
                            '_blank'
                        );
                    },
                    true
                )
            );
        }


        if (pageInfo.type === 'game') {
            const available =
                document.createElement('div');


            if (artifacts.length > 0) {
                available.innerHTML =
                    `🟢 <b>Экипировка доступна</b><br>` +
                    `<span style="color:#aeb6c3">` +
                    `Найдено предметов: ${artifacts.length}` +
                    `</span>`;


                available.style.cssText = `
                    margin-top: 10px;
                    padding: 9px 10px;
                    border-radius: 7px;
                    background: rgba(50,200,100,.10);
                    color: #d9ffe4;
                    font-size: 11px;
                    line-height: 1.45;
                `;

            } else {
                available.innerHTML =
                    `🔒 <b>Информация персонажа закрыта</b><br>` +
                    `<span style="color:#aeb6c3">` +
                    `Экипировка недоступна, но быстрый просмотр работает.` +
                    `</span>`;


                available.style.cssText = `
                    margin-top: 10px;
                    padding: 9px 10px;
                    border-radius: 7px;
                    background: rgba(220,60,60,.10);
                    color: #ffb0b0;
                    font-size: 11px;
                    line-height: 1.45;
                `;
            }


            panel.appendChild(buttons);
            panel.appendChild(available);

        } else {
            panel.appendChild(buttons);
        }


        document.body.appendChild(panel);
    }


    const pageInfo = detectPageType();
    const artifacts = findArtifacts();


    if (pageInfo.type === 'other') {
        return JSON.stringify({
            success: true,
            type: 'other',
            nickname: pageInfo.nickname,
            artifacts: 0
        });
    }


    createDwarToolsPanel(
        pageInfo,
        artifacts
    );


    if (
        pageInfo.type !== 'game' ||
        artifacts.length === 0
    ) {
        return JSON.stringify({
            success: true,
            type: pageInfo.type,
            nickname: pageInfo.nickname,
            gameInfoLink: pageInfo.gameInfoLink,
            artifacts: artifacts.length
        });
    }


    const container = document.createElement('div');
    container.id = CONTAINER_ID;

    container.style.cssText = `
        margin: 20px;
        padding: 15px;
        border: 1px solid #ccc;
        border-radius: 10px;
        box-sizing: border-box;
        background: transparent;
    `;

    // --- Тулбар: Заголовок + Свернуть ---
    const toolbar = document.createElement('div');
    toolbar.style.cssText = `
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 10px;
        font-family: Arial, sans-serif;
        font-size: 12px;
        color: #7a4a00;
    `;

    const titleSpan = document.createElement('span');
    titleSpan.textContent = 'Предметы персонажа';
    titleSpan.style.cssText = `
        font-weight: 700;
        font-size: 13px;
        margin-right: auto;
    `;
    toolbar.appendChild(titleSpan);

    const collapseBtn = document.createElement('button');
    collapseBtn.type = 'button';
    collapseBtn.textContent = 'Свернуть';
    collapseBtn.style.cssText = `
        padding: 3px 10px;
        border: 1px solid #7a4a00;
        background: #ffe2a8;
        color: #7a4a00;
        font-size: 12px;
        border-radius: 4px;
        cursor: pointer;
        font-weight: 600;
    `;
    toolbar.appendChild(collapseBtn);

    container.appendChild(toolbar);

    // --- Контейнер карточек ---
    const cardsContainer = document.createElement('div');
    cardsContainer.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        gap: 20px;
    `;
    container.appendChild(cardsContainer);

    let collapsed = false;

    collapseBtn.addEventListener('click', () => {
        collapsed = !collapsed;
        cardsContainer.style.display = collapsed ? 'none' : 'flex';
        collapseBtn.textContent = collapsed ? 'Развернуть' : 'Свернуть';
    });

    renderCards(cardsContainer, artifacts);


    document.body.prepend(
        container
    );


    return JSON.stringify({
        success: true,
        type: pageInfo.type,
        nickname: pageInfo.nickname,
        gameInfoLink: pageInfo.gameInfoLink,
        artifacts: artifacts.length
    });

})();
"""


# ============================================================
# COLORS
# ============================================================

COLORS = {
    "bg": "#0f1117",
    "panel": "#171a21",
    "panel2": "#1d212b",
    "input": "#11141a",
    "button": "#252b36",
    "button_hover": "#313948",
    "border": "#2c3340",
    "text": "#f1f4f8",
    "secondary": "#9da7b5",
    "accent": "#7c9cff",
    "accent_hover": "#91abff",
    "success": "#61d095",
    "warning": "#e8b45c",
    "error": "#ed7070",
}


# ============================================================
# CHROME / DWARIUM DEVTOOLS
# ============================================================

def get_targets():
    url = f"http://127.0.0.1:{PORT}/json"

    with urllib.request.urlopen(
        url,
        timeout=3
    ) as response:
        return json.load(response)


def get_game_tabs():
    targets = get_targets()

    result = []

    for tab in targets:
        if tab.get("type") != "page":
            continue

        url = tab.get("url", "")

        if not re.search(
            r"^https://w[12]\.dwar\.ru/",
            url,
            re.IGNORECASE
        ):
            continue

        if not tab.get(
            "webSocketDebuggerUrl"
        ):
            continue

        result.append(tab)

    return result


def execute_js(ws_url, code):
    ws = websocket.create_connection(
        ws_url,
        timeout=10,
        origin="http://localhost"
    )

    try:
        ws.send(
            json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": code,
                    "awaitPromise": True,
                    "returnByValue": True
                }
            })
        )

        while True:
            response = json.loads(
                ws.recv()
            )

            if response.get("id") == 1:
                return response

    finally:
        ws.close()


# ============================================================
# ОТКРЫТИЕ НОВОЙ ВКЛАДКИ DWARIUM
# ============================================================

def activate_target(target_id):
    """
    Активирует вкладку Dwarium через DevTools HTTP API.
    """

    if not target_id:
        return False

    url = (
        f"http://127.0.0.1:{PORT}"
        f"/json/activate/{urllib.parse.quote(str(target_id), safe='')}"
    )

    try:
        with urllib.request.urlopen(
            url,
            timeout=3
        ) as response:

            response.read()

        return True

    except Exception:
        return False


def create_new_tab_http(url):
    """
    Создаёт новую вкладку непосредственно в Dwarium.

    Используется PUT /json/new, а не Browser WebSocket
    Target.createTarget.

    Это важно для Dwarium: подключение к Browser WebSocket
    может зависать, тогда как обычные page WebSocket работают.
    """

    encoded_url = urllib.parse.quote(
        url,
        safe=""
    )

    endpoint = (
        f"http://127.0.0.1:{PORT}"
        f"/json/new?{encoded_url}"
    )

    request = urllib.request.Request(
        endpoint,
        method="PUT"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=5
        ) as response:

            raw = response.read()

        if not raw:
            raise RuntimeError(
                "Dwarium вернул пустой ответ при создании вкладки."
            )

        try:
            data = json.loads(
                raw.decode(
                    "utf-8",
                    errors="replace"
                )
            )
        except Exception:
            data = {}

        target_id = data.get(
            "id"
        )

        if not target_id:
            raise RuntimeError(
                "Dwarium создал запрос, но не вернул ID новой вкладки."
            )

        activate_target(
            target_id
        )

        return data

    except urllib.error.HTTPError as error:

        try:
            error_body = error.read().decode(
                "utf-8",
                errors="replace"
            )
        except Exception:
            error_body = ""

        raise RuntimeError(
            "Dwarium не смог создать новую вкладку.\n\n"
            f"HTTP {error.code}\n"
            f"{error_body}"
        )

    except urllib.error.URLError as error:

        raise RuntimeError(
            "Dwarium не отвечает на DevTools HTTP-запрос.\n\n"
            f"{error}"
        )


def wait_for_new_target(
    old_target_ids,
    url,
    timeout=5
):
    """
    Ждёт появления новой вкладки в /json.

    Нужен как дополнительная проверка того,
    что Dwarium действительно создал вкладку.
    """

    deadline = time.time() + timeout

    while time.time() < deadline:

        try:
            targets = get_targets()

        except Exception:
            time.sleep(0.2)
            continue

        for target in targets:

            if target.get("type") != "page":
                continue

            target_id = target.get("id")

            if not target_id:
                continue

            if target_id in old_target_ids:
                continue

            target_url = target.get(
                "url",
                ""
            )

            if (
                target_url == url or
                target_url.startswith(url)
            ):
                return target

        time.sleep(0.2)

    return None


def open_url_in_dwarium(url):
    """
    Открывает URL в новой вкладке уже запущенного Dwarium.

    Основной способ:
        PUT /json/new

    Ранее здесь использовался Browser WebSocket:
        Target.createTarget

    Для текущего Dwarium этот способ иногда зависает.
    Поэтому Browser WebSocket больше не используется.
    """

    tabs = get_game_tabs()

    if not tabs:
        raise RuntimeError(
            "Игровая вкладка Dwarium не найдена.\n\n"
            "Убедитесь, что Dwarium запущен через ярлык "
            "DwarTools с параметрами DevTools."
        )

    old_target_ids = {
        tab.get("id")
        for tab in tabs
        if tab.get("id")
    }

    # --------------------------------------------------------
    # Основной способ.
    # --------------------------------------------------------

    try:

        target = create_new_tab_http(
            url
        )

        target_id = target.get(
            "id"
        )

        if target_id:
            activate_target(
                target_id
            )

        # Проверяем, что вкладка появилась.
        new_target = wait_for_new_target(
            old_target_ids,
            url,
            timeout=3
        )

        if new_target:
            activate_target(
                new_target.get("id")
            )

        return True

    except Exception as primary_error:

        # ----------------------------------------------------
        # Резервный способ.
        #
        # Используем уже существующее подключение к странице.
        # Browser WebSocket здесь НЕ используется.
        # ----------------------------------------------------

        tab, error = find_active_game_tab()

        if not tab:

            raise RuntimeError(
                "Не удалось открыть страницу в Dwarium.\n\n"
                f"{primary_error}\n\n"
                "Активная вкладка Dwarium также не найдена."
            )

        js_url = json.dumps(
            url,
            ensure_ascii=False
        )

        code = f"""
(function () {{
    const url = {js_url};

    const newWindow = window.open(
        url,
        '_blank'
    );

    return {{
        opened: !!newWindow
    }};
}})()
"""

        try:

            result = execute_js(
                tab["webSocketDebuggerUrl"],
                code
            )

            if "error" in result:
                raise RuntimeError(
                    result["error"].get(
                        "message",
                        "Ошибка DevTools."
                    )
                )

            result_data = (
                result
                .get("result", {})
                .get("result", {})
            )

            exception_details = result_data.get(
                "exceptionDetails"
            )

            if exception_details:

                exception = exception_details.get(
                    "exception",
                    {}
                )

                description = exception.get(
                    "description"
                )

                text = exception_details.get(
                    "text",
                    "Ошибка выполнения JavaScript."
                )

                raise RuntimeError(
                    description or text
                )

            value = result_data.get(
                "value"
            )

            if isinstance(value, dict):
                if value.get("opened") is True:
                    return True

            # Даже если window.open не вернул объект,
            # проверяем /json — вкладка могла всё равно появиться.
            new_target = wait_for_new_target(
                old_target_ids,
                url,
                timeout=3
            )

            if new_target:
                activate_target(
                    new_target.get("id")
                )

                return True

            raise RuntimeError(
                "Резервный способ также не смог создать новую вкладку."
            )

        except Exception as fallback_error:

            raise RuntimeError(
                "Не удалось открыть страницу в Dwarium.\n\n"
                "Основной способ:\n"
                f"{primary_error}\n\n"
                "Резервный способ:\n"
                f"{fallback_error}"
            )


# ============================================================
# СОСТОЯНИЕ ВКЛАДКИ
# ============================================================

def get_tab_state(tab):
    code = """
JSON.stringify({
    url: location.href,
    path: location.pathname,
    visibilityState: document.visibilityState,
    hidden: document.hidden,
    hasFocus: document.hasFocus()
})
"""

    result = execute_js(
        tab["webSocketDebuggerUrl"],
        code
    )

    value = (
        result
        .get("result", {})
        .get("result", {})
        .get("value")
    )

    if not value:
        return None

    try:
        return json.loads(value)

    except Exception:
        return None


def find_active_game_tab():

    tabs = get_game_tabs()

    if not tabs:
        return (
            None,
            "Игровая вкладка Dwarium не найдена."
        )

    focused_tabs = []

    for tab in tabs:

        try:

            result = execute_js(
                tab["webSocketDebuggerUrl"],
                """
                JSON.stringify({
                    visibilityState: document.visibilityState,
                    hidden: document.hidden,
                    hasFocus: document.hasFocus()
                })
                """
            )

            value = (
                result
                .get("result", {})
                .get("result", {})
                .get("value")
            )

            if not value:
                continue

            info = json.loads(value)

            if (
                info.get("visibilityState") == "visible"
                and info.get("hasFocus") is True
            ):
                focused_tabs.append(tab)

        except Exception:
            continue


    if len(focused_tabs) == 1:
        return (
            focused_tabs[0],
            None
        )


    visible_tabs = []

    for tab in tabs:

        try:

            result = execute_js(
                tab["webSocketDebuggerUrl"],
                """
                document.visibilityState === "visible"
                """
            )

            value = (
                result
                .get("result", {})
                .get("result", {})
                .get("value")
            )

            if value is True:
                visible_tabs.append(tab)

        except Exception:
            continue


    if len(visible_tabs) == 1:
        return (
            visible_tabs[0],
            None
        )


    if len(tabs) == 1:
        return (
            tabs[0],
            None
        )


    return (
        None,
        "Не удалось определить активную игровую вкладку.\n\n"
        "Переключитесь на нужную вкладку Dwarium."
    )


# ============================================================
# ПРОВЕРКА СТРАНИЦЫ ПЕРСОНАЖА
# ============================================================

def is_character_page(tab):

    code = r"""
(function () {

    const path = location.pathname.toLowerCase();

    const params =
        new URLSearchParams(location.search);

    const nick =
        params.get('nick');


    const buttons = Array.from(
        document.querySelectorAll(
            'input[type="button"], input[type="submit"], button'
        )
    );


    const hasGameInfoButton =
        buttons.some(element => {

            const text = (
                element.value ||
                element.textContent ||
                ''
            ).trim();

            return text ===
                'Перейти к игровой информации';
        });


    const hasArtifactData =
        Array.from(
            document.querySelectorAll(
                'script:not([src])'
            )
        ).some(script => {

            return (
                script.textContent &&
                /art_alt\s*\[\s*["'][^"']+["']\s*\]\s*=/
                    .test(script.textContent)
            );
        });


    const isCharacterPath =
        path.includes('user_info') ||
        path.includes('character') ||
        path.includes('pers_info') ||
        path.includes('player');


    const isNonCharacterPath =
        path.includes('artifact_info') ||
        path.includes('effect_info') ||
        path.includes('companion_info');


    if (hasGameInfoButton) {
        return true;
    }


    if (isCharacterPath && nick) {
        return true;
    }


    if (isCharacterPath && hasArtifactData) {
        return true;
    }


    if (nick && !isNonCharacterPath) {
        return true;
    }


    return false;

})()
"""

    try:

        result = execute_js(
            tab["webSocketDebuggerUrl"],
            code
        )

        return (
            result
            .get("result", {})
            .get("result", {})
            .get("value")
            is True
        )

    except Exception:
        return False


# ============================================================
# INJECT
# ============================================================

def inject_tool(tab):

    result = execute_js(
        tab["webSocketDebuggerUrl"],
        JS_CODE
    )

    result_data = (
        result
        .get("result", {})
        .get("result", {})
    )

    exception_details = \
        result_data.get("exceptionDetails")

    if exception_details:

        exception = exception_details.get(
            "exception",
            {}
        )

        description = exception.get(
            "description"
        )

        text = exception_details.get(
            "text",
            "Ошибка выполнения JavaScript"
        )

        raise RuntimeError(
            description or text
        )


    if "error" in result:

        raise RuntimeError(
            result["error"].get(
                "message",
                "Ошибка DevTools"
            )
        )


    value = result_data.get(
        "value",
        ""
    )


    try:
        return json.loads(value)

    except Exception:
        return {}


# ============================================================
# DWARIUM SHORTCUT / LAUNCHER
# ============================================================

DWARIUM_ARGUMENTS = (
    "--remote-debugging-port=9222 "
    "--remote-allow-origins=*"
)


def ps_escape(value):
    return str(value).replace(
        "'",
        "''"
    )


def get_desktop_path():

    desktop = os.path.join(
        os.path.expanduser("~"),
        "Desktop"
    )

    if os.path.isdir(desktop):
        return desktop

    try:
        import ctypes

        CSIDL_DESKTOPDIRECTORY = 0x10

        buf = ctypes.create_unicode_buffer(
            260
        )

        result = ctypes.windll.shell32.SHGetFolderPathW(
            None,
            CSIDL_DESKTOPDIRECTORY,
            None,
            0,
            buf
        )

        if result == 0 and os.path.isdir(buf.value):
            return buf.value

    except Exception:
        pass

    return desktop


def create_dwarium_shortcut(game_path):

    game_path = os.path.abspath(
        game_path
    )


    if not os.path.isfile(game_path):
        raise FileNotFoundError(
            "Файл Dwarium не найден:\n\n"
            f"{game_path}"
        )


    if not game_path.lower().endswith(".exe"):
        raise ValueError(
            "Необходимо выбрать исполняемый файл Dwarium (.exe)."
        )


    desktop = get_desktop_path()


    if not os.path.isdir(desktop):
        raise RuntimeError(
            "Не удалось определить папку рабочего стола."
        )


    shortcut_path = os.path.join(
        desktop,
        "Dwarium - DwarTools.lnk"
    )


    target = ps_escape(
        game_path
    )

    shortcut = ps_escape(
        shortcut_path
    )

    arguments = ps_escape(
        DWARIUM_ARGUMENTS
    )


    powershell_script = f"""
$ErrorActionPreference = 'Stop'

$WshShell = New-Object -ComObject WScript.Shell

$Shortcut = $WshShell.CreateShortcut('{shortcut}')

$Shortcut.TargetPath = '{target}'
$Shortcut.Arguments = '{arguments}'
$Shortcut.WorkingDirectory = Split-Path -Parent '{target}'
$Shortcut.IconLocation = '{target},0'
$Shortcut.Description = 'Dwarium с поддержкой DwarTools DevTools'

$Shortcut.Save()
"""


    try:

        powershell_exe = (
            os.environ.get("SystemRoot", r"C:\Windows")
            + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
        )

        if not os.path.isfile(
            powershell_exe
        ):
            powershell_exe = "powershell.exe"


        result = subprocess.run(
            [
                powershell_exe,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15
        )


    except Exception as error:

        raise RuntimeError(
            "Не удалось запустить PowerShell для создания ярлыка.\n\n"
            f"{error}"
        )


    if result.returncode != 0:

        error_text = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Неизвестная ошибка PowerShell."
        )

        raise RuntimeError(
            "Windows не смог создать ярлык.\n\n"
            f"{error_text}"
        )


    if not os.path.exists(
        shortcut_path
    ):

        raise RuntimeError(
            "Команда создания ярлыка завершилась без ошибки, "
            "но файл ярлыка не появился."
        )


    return shortcut_path


def select_dwarium_exe():

    from tkinter import filedialog

    path = filedialog.askopenfilename(
        title="Выберите файл Dwarium",
        filetypes=[
            (
                "Исполняемые файлы",
                "*.exe"
            ),
            (
                "Все файлы",
                "*.*"
            )
        ]
    )

    return path


def create_dwarium_shortcut_from_gui():

    path = dwarium_path_var.get().strip()


    if not path:

        messagebox.showwarning(
            "DwarTools",
            "Сначала выберите файл Dwarium.exe."
        )

        return


    if not os.path.isfile(path):

        messagebox.showerror(
            "DwarTools",
            "Указанный файл не найден:\n\n"
            f"{path}"
        )

        return


    try:

        shortcut = create_dwarium_shortcut(
            path
        )


        set_status(
            "● Ярлык Dwarium создан",
            COLORS["success"]
        )


        messagebox.showinfo(
            "DwarTools",
            "Ярлык успешно создан на рабочем столе.\n\n"
            f"{shortcut}\n\n"
            "Теперь запускайте Dwarium через этот ярлык."
        )


    except Exception as error:

        set_status(
            "✕ Не удалось создать ярлык",
            COLORS["error"]
        )


        messagebox.showerror(
            "DwarTools",
            str(error)
        )


def choose_dwarium_file():

    path = select_dwarium_exe()


    if not path:
        return


    dwarium_path_var.set(
        path
    )


    set_status(
        "● Файл Dwarium выбран",
        COLORS["accent"]
    )


# ============================================================
# GUI
# ============================================================

root = tk.Tk()

root.title(
    "DwarTools"
)

root.geometry(
    "620x720"
)

root.minsize(
    580,
    650
)

root.configure(
    background=COLORS["bg"]
)

root.resizable(
    True,
    True
)


# ============================================================
# TTK STYLE
# ============================================================

style = ttk.Style(
    root
)


try:
    style.theme_use(
        "clam"
    )
except tk.TclError:
    pass


style.configure(
    "Main.TFrame",
    background=COLORS["bg"]
)

style.configure(
    "Panel.TFrame",
    background=COLORS["panel"]
)

style.configure(
    "Inner.TFrame",
    background=COLORS["panel2"]
)

style.configure(
    "Title.TLabel",
    background=COLORS["bg"],
    foreground=COLORS["text"],
    font=("Segoe UI", 19, "bold")
)

style.configure(
    "Subtitle.TLabel",
    background=COLORS["bg"],
    foreground=COLORS["secondary"],
    font=("Segoe UI", 9)
)

style.configure(
    "Section.TLabel",
    background=COLORS["panel"],
    foreground=COLORS["text"],
    font=("Segoe UI", 10, "bold")
)

style.configure(
    "Normal.TLabel",
    background=COLORS["panel"],
    foreground=COLORS["secondary"],
    font=("Segoe UI", 9)
)

style.configure(
    "Status.TLabel",
    background=COLORS["panel2"],
    foreground=COLORS["accent"],
    font=("Segoe UI", 9, "bold"),
    padding=(10, 8)
)

style.configure(
    "Dwar.TButton",
    background=COLORS["button"],
    foreground=COLORS["text"],
    borderwidth=0,
    focusthickness=0,
    padding=(12, 9),
    font=("Segoe UI", 9, "bold")
)

style.map(
    "Dwar.TButton",
    background=[
        ("active", COLORS["button_hover"]),
        ("pressed", COLORS["accent"])
    ],
    foreground=[
        ("pressed", "#ffffff")
    ]
)

style.configure(
    "Accent.TButton",
    background=COLORS["accent"],
    foreground="#ffffff",
    borderwidth=0,
    focusthickness=0,
    padding=(12, 10),
    font=("Segoe UI", 9, "bold")
)

style.map(
    "Accent.TButton",
    background=[
        ("active", COLORS["accent_hover"]),
        ("pressed", "#6c88e0")
    ]
)

style.configure(
    "Nick.TEntry",
    fieldbackground=COLORS["input"],
    foreground=COLORS["text"],
    insertcolor=COLORS["text"],
    bordercolor=COLORS["border"],
    lightcolor=COLORS["border"],
    darkcolor=COLORS["border"],
    padding=(10, 8),
    font=("Segoe UI", 10)
)

style.configure(
    "Footer.TLabel",
    background=COLORS["bg"],
    foreground="#687282",
    font=("Segoe UI", 8)
)


# ============================================================
# HEADER
# ============================================================

main = ttk.Frame(
    root,
    style="Main.TFrame"
)

main.pack(
    fill="both",
    expand=True
)


header = ttk.Frame(
    main,
    style="Main.TFrame"
)

header.pack(
    fill="x",
    padx=24,
    pady=(22, 16)
)


title_frame = ttk.Frame(
    header,
    style="Main.TFrame"
)

title_frame.pack(
    side="left",
    fill="x",
    expand=True
)


title_label = ttk.Label(
    title_frame,
    text="⚔ DwarTools",
    style="Title.TLabel"
)

title_label.pack(
    anchor="w"
)


subtitle_label = ttk.Label(
    title_frame,
    text="Инструменты для Dwarium",
    style="Subtitle.TLabel"
)

subtitle_label.pack(
    anchor="w",
    pady=(2, 0)
)


server_badge = tk.Label(
    header,
    text="DEVTOOLS",
    bg="#202633",
    fg=COLORS["accent"],
    font=("Segoe UI", 8, "bold"),
    padx=9,
    pady=5
)

server_badge.pack(
    side="right",
    anchor="n"
)


# ============================================================
# MAIN PANEL
# ============================================================

panel = ttk.Frame(
    main,
    style="Panel.TFrame"
)

panel.pack(
    fill="both",
    expand=True,
    padx=24
)


# ============================================================
# STATUS
# ============================================================

status_title = ttk.Label(
    panel,
    text="Состояние",
    style="Section.TLabel"
)

status_title.pack(
    anchor="w",
    padx=18,
    pady=(18, 7)
)


status_box = ttk.Frame(
    panel,
    style="Inner.TFrame"
)

status_box.pack(
    fill="x",
    padx=18
)


status = ttk.Label(
    status_box,
    text="● Ожидание",
    style="Status.TLabel"
)

status.pack(
    fill="x"
)


# ============================================================
# NICKNAME
# ============================================================

nick_title = ttk.Label(
    panel,
    text="Быстрый просмотр персонажа",
    style="Section.TLabel"
)

nick_title.pack(
    anchor="w",
    padx=18,
    pady=(20, 7)
)


nick_description = ttk.Label(
    panel,
    text="Введите ник, чтобы открыть тень или эффекты.",
    style="Normal.TLabel"
)

nick_description.pack(
    anchor="w",
    padx=18,
    pady=(0, 8)
)


nick_row = ttk.Frame(
    panel,
    style="Panel.TFrame"
)

nick_row.pack(
    fill="x",
    padx=18
)


nickname_var = tk.StringVar()


nickname_entry = ttk.Entry(
    nick_row,
    textvariable=nickname_var,
    style="Nick.TEntry"
)

nickname_entry.pack(
    side="left",
    fill="x",
    expand=True
)


def paste_nickname(event):

    try:
        text = root.clipboard_get()

    except tk.TclError:
        return "break"


    try:

        nickname_entry.delete(
            0,
            tk.END
        )

        nickname_entry.insert(
            0,
            text
        )

    except Exception:
        pass


    return "break"


def select_all_nickname(event):

    nickname_entry.select_range(
        0,
        tk.END
    )

    nickname_entry.icursor(
        tk.END
    )

    return "break"


def copy_nickname(event):

    try:
        nickname_entry.event_generate(
            "<<Copy>>"
        )
    except Exception:
        pass

    return "break"


def cut_nickname(event):

    try:
        nickname_entry.event_generate(
            "<<Cut>>"
        )
    except Exception:
        pass

    return "break"


def nickname_keyboard(event):

    if event.state & 0x0004:

        if event.keycode == 86:
            return paste_nickname(event)

        if event.keycode == 65:
            return select_all_nickname(event)

        if event.keycode == 67:
            return copy_nickname(event)

        if event.keycode == 88:
            return cut_nickname(event)

    return None


nickname_entry.bind(
    "<KeyPress>",
    nickname_keyboard
)


nickname_entry.bind(
    "<Shift-Insert>",
    paste_nickname
)


# ============================================================
# CURRENT SERVER
# ============================================================

def get_current_server():

    try:

        tab, error = find_active_game_tab()

        if tab:

            url = tab.get(
                "url",
                ""
            )

            match = re.search(
                r"https://(w[12])\.dwar\.ru/",
                url,
                re.IGNORECASE
            )

            if match:
                return match.group(1).lower()

    except Exception:
        pass


    return "w1"


# ============================================================
# QUICK CHARACTER VIEW
# ============================================================

def open_nick_page(kind):

    nickname = nickname_entry.get().strip()


    if not nickname:

        messagebox.showwarning(
            "DwarTools",
            "Введите ник персонажа."
        )

        nickname_entry.focus_set()

        return


    server = get_current_server()


    encoded_nick = urllib.parse.quote(
        nickname,
        safe=""
    )


    if kind == "shadow":

        url = (
            f"https://{server}.dwar.ru/"
            f"companion_info.php?nick={encoded_nick}"
        )

        title = "Тень"

    else:

        url = (
            f"https://{server}.dwar.ru/"
            f"effect_info.php?nick={encoded_nick}"
        )

        title = "Эффекты"


    set_status(
        f"● Открытие {title}...",
        COLORS["warning"]
    )


    root.update_idletasks()


    try:

        open_url_in_dwarium(
            url
        )


        set_status(
            f"● {title}: {nickname}",
            COLORS["accent"]
        )


    except Exception as error:

        set_status(
            "✕ Не удалось открыть страницу",
            COLORS["error"]
        )


        messagebox.showerror(
            "DwarTools",
            "Не удалось открыть страницу в Dwarium.\n\n"
            f"{error}"
        )


# ============================================================
# QUICK VIEW BUTTONS
# ============================================================

shadow_button = ttk.Button(
    nick_row,
    text="👻  Тень",
    style="Dwar.TButton",
    command=lambda: open_nick_page(
        "shadow"
    )
)

shadow_button.pack(
    side="left",
    padx=(8, 0)
)


effects_button = ttk.Button(
    nick_row,
    text="✨  Эффекты",
    style="Dwar.TButton",
    command=lambda: open_nick_page(
        "effects"
    )
)

effects_button.pack(
    side="left",
    padx=(7, 0)
)


# ============================================================
# DWARIUM CONNECTION / SHORTCUT
# ============================================================

connection_title = ttk.Label(
    panel,
    text="Подключение Dwarium",
    style="Section.TLabel"
)

connection_title.pack(
    anchor="w",
    padx=18,
    pady=(20, 7)
)


connection_description = ttk.Label(
    panel,
    text=(
        "Для автоматического подключения DwarTools к Dwarium "
        "необходимо запускать игру с параметрами DevTools."
    ),
    style="Normal.TLabel",
    wraplength=470,
    justify="left"
)

connection_description.pack(
    anchor="w",
    padx=18,
    pady=(0, 10)
)


# ============================================================
# NOTEBOOK
# ============================================================

connection_notebook = ttk.Notebook(
    panel
)

connection_notebook.pack(
    fill="x",
    padx=18
)


# ============================================================
# AUTO TAB
# ============================================================

auto_tab = ttk.Frame(
    connection_notebook,
    style="Panel.TFrame"
)

connection_notebook.add(
    auto_tab,
    text="Автоматически"
)


auto_info = ttk.Label(
    auto_tab,
    text=(
        "1. Выберите файл Dwarium.exe.\n"
        "2. DwarTools создаст специальный ярлык на рабочем столе.\n"
        "3. Запускайте игру через этот ярлык."
    ),
    style="Normal.TLabel",
    wraplength=450,
    justify="left"
)

auto_info.pack(
    anchor="w",
    padx=12,
    pady=(12, 10)
)


dwarium_path_var = tk.StringVar()


dwarium_path_entry = ttk.Entry(
    auto_tab,
    textvariable=dwarium_path_var,
    style="Nick.TEntry"
)

dwarium_path_entry.pack(
    fill="x",
    padx=12,
    pady=(0, 8)
)


auto_buttons = ttk.Frame(
    auto_tab,
    style="Panel.TFrame"
)

auto_buttons.pack(
    fill="x",
    padx=12,
    pady=(0, 12)
)


choose_exe_button = ttk.Button(
    auto_buttons,
    text="📁 Выбрать Dwarium.exe",
    style="Dwar.TButton",
    command=choose_dwarium_file
)

choose_exe_button.pack(
    side="left",
    fill="x",
    expand=True
)


create_shortcut_button = ttk.Button(
    auto_buttons,
    text="🔗 Создать ярлык",
    style="Accent.TButton",
    command=create_dwarium_shortcut_from_gui
)

create_shortcut_button.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(8, 0)
)


# ============================================================
# MANUAL TAB
# ============================================================

manual_tab = ttk.Frame(
    connection_notebook,
    style="Panel.TFrame"
)

connection_notebook.add(
    manual_tab,
    text="Вручную"
)


manual_text = tk.Text(
    manual_tab,
    height=10,
    wrap="word",
    background=COLORS["input"],
    foreground=COLORS["text"],
    insertbackground=COLORS["text"],
    selectbackground=COLORS["accent"],
    selectforeground="#ffffff",
    relief="flat",
    borderwidth=0,
    font=("Segoe UI", 9),
    padx=12,
    pady=12
)

manual_text.pack(
    fill="x",
    padx=12,
    pady=12
)


manual_text.insert(
    "1.0",
    "РУЧНОЙ СПОСОБ\n"
    "\n"
    "1. Найдите ярлык, которым запускаете Dwarium.\n"
    "\n"
    "2. Нажмите по нему правой кнопкой мыши → "
    "«Свойства».\n"
    "\n"
    "3. Откройте вкладку «Ярлык».\n"
    "\n"
    "4. В поле «Объект» после пути к Dwarium.exe "
    "добавьте пробел и параметры:\n"
    "\n"
    "--remote-debugging-port=9222 --remote-allow-origins=*\n"
    "\n"
    "Пример:\n"
    "\"C:\\Dwarium\\Dwarium.exe\" "
    "--remote-debugging-port=9222 --remote-allow-origins=*\n"
    "\n"
    "5. Нажмите «Применить» → «ОК».\n"
    "\n"
    "6. Полностью закройте Dwarium и запустите его "
    "через изменённый ярлык.\n"
    "\n"
    "ВАЖНО:\n"
    "Если Dwarium уже запущен без этих параметров, "
    "DwarTools не сможет подключиться к DevTools.\n"
)


manual_text.configure(
    state="disabled"
)


# ============================================================
# MAIN BUTTON
# ============================================================

run_button = ttk.Button(
    panel,
    text="▶  Запустить DwarTools",
    style="Accent.TButton"
)

run_button.pack(
    fill="x",
    padx=18,
    pady=(20, 8)
)


# ============================================================
# EXTRA BUTTONS
# ============================================================

buttons_row = ttk.Frame(
    panel,
    style="Panel.TFrame"
)

buttons_row.pack(
    fill="x",
    padx=18
)


def open_github():

    webbrowser.open_new_tab(
        GITHUB_URL
    )


def open_links():

    webbrowser.open_new_tab(
        USEFUL_LINKS_URL
    )


github_button = ttk.Button(
    buttons_row,
    text="GitHub",
    style="Dwar.TButton",
    command=open_github
)

github_button.pack(
    side="left",
    fill="x",
    expand=True
)


links_button = ttk.Button(
    buttons_row,
    text="Полезные ссылки",
    style="Dwar.TButton",
    command=open_links
)

links_button.pack(
    side="left",
    fill="x",
    expand=True,
    padx=(7, 0)
)


# ============================================================
# FOOTER
# ============================================================

footer = ttk.Frame(
    main,
    style="Main.TFrame"
)

footer.pack(
    fill="x",
    padx=24,
    pady=(12, 15)
)


footer_label = ttk.Label(
    footer,
    text="DwarTools  •  автоматическое подключение к Dwarium",
    style="Footer.TLabel"
)

footer_label.pack(
    side="left"
)


version_label = ttk.Label(
    footer,
    text="v0.8",
    style="Footer.TLabel"
)

version_label.pack(
    side="right"
)


# ============================================================
# STATUS
# ============================================================

def set_status(
    text,
    color=None
):

    if color is None:
        color = COLORS["accent"]


    status.configure(
        text=text,
        foreground=color
    )


    root.update_idletasks()


# ============================================================
# RUN TOOL
# ============================================================

last_injected_url = None
last_injected_tab_id = None
auto_injection_running = False


def run_tool(
    show_errors=True
):

    global last_injected_url
    global last_injected_tab_id


    try:

        tab, error = find_active_game_tab()


        if not tab:

            raise RuntimeError(
                error or
                "Не удалось определить активную "
                "игровую вкладку."
            )


        set_status(
            "● Проверка страницы...",
            COLORS["warning"]
        )


        if not is_character_page(tab):

            set_status(
                "● Откройте страницу персонажа",
                COLORS["secondary"]
            )

            return False


        set_status(
            "● Запуск DwarTools...",
            COLORS["warning"]
        )


        info = inject_tool(
            tab
        )


        current_url = tab.get(
            "url",
            ""
        )


        current_tab_id = tab.get(
            "id"
        )


        last_injected_url = current_url
        last_injected_tab_id = current_tab_id


        if info.get(
            "type"
        ) == "appearance":

            nickname = info.get(
                "nickname"
            )


            set_status(
                "● Страница персонажа" +
                (
                    f": {nickname}"
                    if nickname
                    else ""
                ),
                COLORS["accent"]
            )


        elif info.get(
            "artifacts",
            0
        ) > 0:

            set_status(
                f"● Экипировка: "
                f"{info['artifacts']} предметов",
                COLORS["success"]
            )


        else:

            set_status(
                "● Панель персонажа активна",
                COLORS["accent"]
            )


        return True


    except Exception as error:

        set_status(
            "✕ Ошибка выполнения",
            COLORS["error"]
        )


        if show_errors:

            messagebox.showerror(
                "DwarTools v0.8",
                str(error)
            )


        return False


run_button.configure(
    command=run_tool
)


# ============================================================
# AUTOMATIC MONITOR
# ============================================================

auto_last_url = None
auto_last_page = None
auto_busy = False


# ============================================================
# AUTOMATIC MONITOR (BACKGROUND THREAD)
# ------------------------------------------------------------
# Раньше automatic_check() выполнялся в основном потоке tkinter и
# каждые ~1.2 секунды делал блокирующий HTTP-запрос к DevTools
# (timeout=3 секунды). Если Dwarium не запущен — запрос висел до
# таймаута, всё это время окно не могло обрабатывать события мыши
# и перемещалось рывками.
#
# Теперь мониторинг крутится в фоновом потоке, а статусы
# передаются в основной поток через queue. GUI больше не виснет.
# ============================================================

_monitor_queue = _queue.Queue()
_monitor_stop = threading.Event()
_monitor_thread = None


def _push_status(text, color=None):
    """Положить статус в очередь — основной поток применит его."""
    _monitor_queue.put(("status", text, color))


def _process_monitor_queue():
    """Раз в 100мс читаем очередь и обновляем UI.
    Вызывается только в основном потоке tkinter через root.after."""
    try:
        while True:
            item = _monitor_queue.get_nowait()
            kind = item[0]
            if kind == "status":
                _, text, color = item
                set_status(text, color)
    except _queue.Empty:
        pass

    root.after(100, _process_monitor_queue)


def _dwarium_monitor_worker():
    """Фоновый поток: постоянно проверяет Dwarium.
    Все блокирующие операции (HTTP/WebSocket к DevTools) выполняются
    здесь, не замораживая GUI."""
    global auto_last_url
    global auto_last_page

    while not _monitor_stop.is_set():
        try:
            tabs = get_game_tabs()

            if not tabs:
                _push_status(
                    "● Ожидание Dwarium...",
                    COLORS["secondary"]
                )
                # Долгая пауза, когда Dwarium не запущен —
                # нечего его спамить запросами.
                if _monitor_stop.wait(3.0):
                    break
                continue

            tab, error = find_active_game_tab()

            if not tab:
                _push_status(
                    "● Ожидание Dwarium...",
                    COLORS["secondary"]
                )
                if _monitor_stop.wait(2.0):
                    break
                continue

            url = tab.get("url", "")
            tab_id = tab.get("id")

            if (
                url == auto_last_url
                and tab_id == auto_last_page
            ):
                if _monitor_stop.wait(1.2):
                    break
                continue

            if not is_character_page(tab):
                _push_status(
                    "● Загрузка страницы персонажа...",
                    COLORS["warning"]
                )
                if _monitor_stop.wait(1.2):
                    break
                continue

            _push_status(
                "● Автозапуск DwarTools...",
                COLORS["warning"]
            )

            try:
                info = inject_tool(tab)
            except Exception:
                _push_status(
                    "● Ожидание полной загрузки страницы...",
                    COLORS["warning"]
                )
                if _monitor_stop.wait(1.2):
                    break
                continue

            if (
                not info
                or info.get("success") is not True
            ):
                _push_status(
                    "● Ожидание загрузки DwarTools...",
                    COLORS["warning"]
                )
                if _monitor_stop.wait(1.2):
                    break
                continue

            auto_last_url = url
            auto_last_page = tab_id

            if info.get("type") == "appearance":
                nickname = info.get("nickname")
                _push_status(
                    "● Персонаж" +
                    (f": {nickname}" if nickname else ""),
                    COLORS["accent"]
                )
            elif info.get("artifacts", 0) > 0:
                _push_status(
                    f"● Экипировка: "
                    f"{info['artifacts']} предметов",
                    COLORS["success"]
                )
            else:
                _push_status(
                    "● Панель персонажа активна",
                    COLORS["accent"]
                )

        except Exception:
            _push_status(
                "● Ожидание Dwarium DevTools...",
                COLORS["secondary"]
            )
            if _monitor_stop.wait(2.0):
                break


def _start_dwarium_monitor():
    """Запускает фоновый поток мониторинга и обработчик очереди."""
    global _monitor_thread

    _monitor_stop.clear()

    _monitor_thread = threading.Thread(
        target=_dwarium_monitor_worker,
        daemon=True,
        name="DwariumMonitor"
    )
    _monitor_thread.start()

    # Запускаем периодическое чтение очереди в основном потоке
    root.after(100, _process_monitor_queue)


def _stop_dwarium_monitor():
    """Останавливает фоновый поток мониторинга.
    Вызывается при закрытии окна."""
    _monitor_stop.set()


# ============================================================
# START AUTOMATIC MONITORING
# ============================================================

def start_automatic_monitor():
    _start_dwarium_monitor()


# ============================================================
# INITIAL CONNECTION
# ============================================================

def initial_connection_check():

    try:

        get_targets()


        set_status(
            "● DevTools подключён • ожидание Dwarium",
            COLORS["accent"]
        )


    except Exception:

        set_status(
            "● Ожидание Dwarium DevTools...",
            COLORS["secondary"]
        )


root.after(
    300,
    initial_connection_check
)


start_automatic_monitor()


# ============================================================
# ENTER IN NICKNAME
# ============================================================

nickname_entry.bind(
    "<Return>",
    lambda event: open_nick_page(
        "shadow"
    )
)


# ============================================================
# CLOSE
# ============================================================

def on_close():
    _stop_dwarium_monitor()
    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# MAINLOOP
# ============================================================

root.mainloop()
