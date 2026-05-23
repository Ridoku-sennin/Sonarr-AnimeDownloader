import { useState, useEffect } from 'react';

import { Card } from '../Card';

import type { API, DownloadProgress } from '@/utils/API';

import './style.scss';

interface DownloadsProps {
    api: API,
    pollInterval?: number
}

export function Downloads({ api, pollInterval = 1000 }: DownloadsProps) {
    const [downloads, setDownloads] = useState<DownloadProgress[]>([]);

    useEffect(() => {
        let cancelled = false;

        async function tick() {
            try {
                const res = await api.getDownloads();
                if (!cancelled) setDownloads(res);
            } catch {
                if (!cancelled) setDownloads([]);
            }
        }

        tick();
        const id = setInterval(tick, pollInterval);
        return () => { cancelled = true; clearInterval(id); };
    }, [api, pollInterval]);

    if (downloads.length === 0) return null;

    return (
        <Card className='downloads'>
            <h2>Download ({downloads.length})</h2>
            <section id='downloads'>
                {downloads.map(d => <DownloadRow key={d.title} download={d} />)}
            </section>
        </Card>
    );
}

interface DownloadRowProps {
    download: DownloadProgress
}

function DownloadRow({ download }: DownloadRowProps) {
    const pct = Math.max(0, Math.min(1, download.percentage ?? 0));
    return (
        <div className='download-row'>
            <span className='name'>{download.title}</span>
            <span className='size'>
                {formatBytes(download.downloaded_bytes)} / {formatBytes(download.total_bytes)}
            </span>
            <div className='progress'>
                <label>{(pct * 100).toFixed(1)}%</label>
                <span style={{ width: `calc(${pct * 100}% - 0px)` }}></span>
            </div>
            <time className='elapsed'>{formatTime(download.elapsed)}</time>
            <span className='speed'>{formatSpeed(download.speed)}</span>
            <time className='eta'>{formatTime(download.eta)}</time>
        </div>
    );
}

function formatBytes(n?: number): string {
    if (n === undefined || n === null || isNaN(n)) return '-';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let v = n;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function formatSpeed(n?: number): string {
    if (n === undefined || n === null || isNaN(n)) return '-';
    return `${formatBytes(n)}/s`;
}

function formatTime(s?: number): string {
    if (s === undefined || s === null || isNaN(s) || !isFinite(s)) return '--:--:--';
    const sec = Math.max(0, Math.floor(s));
    const h = Math.floor(sec / 3600).toString().padStart(2, '0');
    const m = Math.floor((sec % 3600) / 60).toString().padStart(2, '0');
    const r = (sec % 60).toString().padStart(2, '0');
    return `${h}:${m}:${r}`;
}
