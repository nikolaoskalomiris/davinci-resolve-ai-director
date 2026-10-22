const { contextBridge, ipcRenderer } = require('electron/renderer');

contextBridge.exposeInMainWorld('aiDirector', {
    getBridgeStatus: () =>
        ipcRenderer.invoke('aid:getBridgeStatus'),

    getBackendStatus: () =>
        ipcRenderer.invoke('aid:getBackendStatus'),

    getContextStatus: () =>
        ipcRenderer.invoke('aid:getContextStatus'),

    getServerStatus: () =>
        ipcRenderer.invoke('aid:getServerStatus'),

    getServerProfile: () =>
        ipcRenderer.invoke('aid:getServerProfile'),

    setServerProfile: (profileId) =>
        ipcRenderer.invoke('aid:setServerProfile', String(profileId || '')),

    getSettingsState: () =>
        ipcRenderer.invoke('aid:getSettingsState'),

    rescanModels: () =>
        ipcRenderer.invoke('aid:rescanModels'),

    applySettings: (settings) =>
        ipcRenderer.invoke('aid:applySettings', settings || {}),

    locateExternalFfmpeg: () =>
        ipcRenderer.invoke('aid:locateExternalFfmpeg'),

    openRecommendedFfmpeg: () =>
        ipcRenderer.invoke('aid:openRecommendedFfmpeg'),

    setAppearanceSkin: (skin) =>
        ipcRenderer.invoke('aid:setAppearanceSkin', String(skin || '')),

    setDebugMode: (enabled) =>
        ipcRenderer.invoke('aid:setDebugMode', Boolean(enabled)),

    getUpdateStatus: () =>
        ipcRenderer.invoke('aid:getUpdateStatus'),

    checkUpdates: () =>
        ipcRenderer.invoke('aid:checkUpdates'),

    installUpdate: (component) =>
        ipcRenderer.invoke('aid:installUpdate', component),

    startServer: () =>
        ipcRenderer.invoke('aid:startServer'),

    stopServer: () =>
        ipcRenderer.invoke('aid:stopServer'),

    chat: (message, clientRequestId = null) =>
        ipcRenderer.invoke('aid:chat', message, clientRequestId),

    stopChat: (options = {}) =>
        ipcRenderer.invoke('aid:stopChat', options),

    clearSession: (options = {}) =>
        ipcRenderer.invoke('aid:clearSession', options),

    showChatContextMenu: (markdown, options = {}) =>
        ipcRenderer.invoke('aid:showChatContextMenu', markdown, options),

    showInputContextMenu: () =>
        ipcRenderer.invoke('aid:showInputContextMenu'),

    onResolveStatus: (callback) => {
        ipcRenderer.on(
            'aid:resolveStatus',
            (_event, status) => callback(status)
        );
    },


    onBackendStatus: (callback) => {
        ipcRenderer.on(
            'aid:backendStatus',
            (_event, status) => callback(status)
        );
    },

    onContextStatus: (callback) => {
        ipcRenderer.on(
            'aid:contextStatus',
            (_event, status) => callback(status)
        );
    },

    onUpdateStatus: (callback) => {
        ipcRenderer.on(
            'aid:updateStatus',
            (_event, status) => callback(status)
        );
    },

    onChatProgress: (callback) => {
        ipcRenderer.on(
            'aid:chatProgress',
            (_event, payload) => callback(payload)
        );
    },

    onChatClear: (callback) => {
        ipcRenderer.on(
            'aid:clearChat',
            () => callback()
        );
    },

    onServerStatus: (callback) => {
        ipcRenderer.on(
            'aid:serverStatus',
            (_event, status) => callback(status)
        );
    }
});
