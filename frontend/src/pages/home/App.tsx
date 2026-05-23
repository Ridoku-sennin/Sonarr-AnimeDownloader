// import * from "react";
import { useState, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import { Table, Container, Navigator } from '@/components';

import './style.scss';

import { API } from '@/utils/API';
import { ToastContainer, toast } from '@/helper';

export default function App() {

    const [version, setVersion] = useState('');
    const [navActive, setNavActive] = useState(false);
    const [tableReloadKey, setTableReloadKey] = useState(0);

    const api = new API(BACKEND);

    useEffect(() => {
        api.getVersion().then(res => setVersion(res));
    }, []);

    function onImportChange(e: ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (!file) return;
        api.importTable(file).then(res => {
            toast(res.message ?? "Tabella caricata con successo.");
            setTableReloadKey(k => k + 1);
        });
        e.target.value = '';
    }

    return (<>
        <Navigator
            activationState={[navActive, setNavActive]}
        >
            <a>Home</a>
            <a href="settings.html">Settings</a>
            <a href="log.html">Log</a>
        </Navigator>

        <Container
            title='Tabella Di Conversione'
            version={version}
            navigatorState={[navActive, setNavActive]}
            onRescan={() => api.putWekeup().then(res => toast(res.message))}
        >
            <Table api={api} key={tableReloadKey}/>
            <section className="ie-bottom">
                <a className="btn" id="export" href={api.getTableExportUrl()} target="_blank" title="Esporta tabella">
                    <i>file_download</i>
                </a>
                <label htmlFor="import" className="btn" title="Importa tabella">
                    <input id="import" type="file" accept=".json" onChange={onImportChange}/>
                    <i>file_upload</i>
                </label>
            </section>
        </Container>
        <ToastContainer/>
    </>);

}
