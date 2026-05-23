import type { API } from '@/utils/API';

import { Card } from '../Card';

import { useState, useEffect, useRef } from 'react';
import { AnsiUp } from 'ansi_up';
import { io, Socket } from 'socket.io-client';

import './style.scss';

interface LogViewerProps {
    api: API,
    refreshKey?: number
}

const ansi = new AnsiUp();

export function LogViewer({ api, refreshKey = 0 }: LogViewerProps) {
    const [logs, setLogs] = useState<string[]>([]);
    const [olderPage, setOlderPage] = useState(0);
    const [reachedTop, setReachedTop] = useState(false);
    const stickToBottomRef = useRef(true);
    const containerRef = useRef<HTMLDivElement>(null);

    function scrollToBottomIfSticky() {
        const c = containerRef.current;
        if (c && stickToBottomRef.current) {
            c.scrollTop = c.scrollHeight;
        }
    }

    // Fetch iniziale + reset su rescan
    useEffect(() => {
        let cancelled = false;
        api.getLog(0).then(res => {
            if (cancelled) return;
            setLogs(res);
            setOlderPage(1);
            setReachedTop(false);
            requestAnimationFrame(scrollToBottomIfSticky);
        });
        return () => { cancelled = true; };
    }, [api, refreshKey]);

    // Push real-time via SocketIO
    useEffect(() => {
        // Se backend è assoluto (http/https) usa quello, altrimenti lascia che socket.io usi current origin
        const isAbsolute = /^https?:\/\//.test(api.backend);
        const socketUrl = isAbsolute ? api.backend.replace(/\/api$/, '') : undefined;
        // Default transport order ['polling', 'websocket']: connette subito via polling
        // poi tenta upgrade a websocket (silenzioso se non supportato)
        const socket: Socket = socketUrl ? io(socketUrl) : io();

        socket.on('log', (data: string) => {
            setLogs(prev => [...prev, data]);
            requestAnimationFrame(scrollToBottomIfSticky);
        });

        return () => {
            socket.off('log');
            socket.disconnect();
        };
    }, [api]);

    // Scroll handler: stick-to-bottom + caricamento storico in alto
    function handleScroll() {
        const c = containerRef.current;
        if (!c) return;
        const distanceFromBottom = c.scrollHeight - (c.scrollTop + c.clientHeight);
        stickToBottomRef.current = distanceFromBottom < 60;

        if (c.scrollTop <= 50 && !reachedTop) {
            loadOlder();
        }
    }

    async function loadOlder() {
        if (reachedTop) return;
        const c = containerRef.current;
        if (!c) return;
        const res = await api.getLog(olderPage);
        if (res.length === 0) {
            setReachedTop(true);
            return;
        }
        const oldHeight = c.scrollHeight;
        setLogs(prev => [...res, ...prev]);
        setOlderPage(p => p + 1);
        requestAnimationFrame(() => {
            const newHeight = c.scrollHeight;
            c.scrollTop = newHeight - oldHeight;
        });
    }

    return (
        <Card className='log'>
            <div className='log-content' ref={containerRef} onScroll={handleScroll}>
                <ul id='log'>
                    {logs.map((l, i) =>
                        <li
                            key={i}
                            dangerouslySetInnerHTML={{ __html: ansi.ansi_to_html(l) }}
                        />
                    )}
                </ul>
            </div>
        </Card>
    );
}
