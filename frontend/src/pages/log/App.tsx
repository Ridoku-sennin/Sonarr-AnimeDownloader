import { useState, useEffect } from 'react';

import { Container, Navigator, LogViewer, Downloads } from '@/components';

import { API } from '@/utils/API';
import { ToastContainer, toast } from '@/helper';

import './style.scss';

export default function App() {

    const [version, setVersion] = useState('');
    const [navActive, setNavActive] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);

    const api = new API(BACKEND);

    useEffect(() => {
        api.getVersion().then(res => setVersion(res));
    }, []);

    function rescan() {
        api.putWekeup().then(res => {
            toast(res.message);
            setRefreshKey(k => k + 1);
        });
    }

    return (<>
        <Navigator
            activationState={[navActive, setNavActive]}
        >
            <a href="index.html">Home</a>
            <a href="settings.html">Settings</a>
            <a>Log</a>
        </Navigator>

        <Container
            title='Log'
            version={version}
            navigatorState={[navActive, setNavActive]}
            onRescan={rescan}
        >
            <LogViewer api={api} refreshKey={refreshKey} />
            <Downloads api={api} />
        </Container>
        <ToastContainer />
    </>);
}
