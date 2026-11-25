const browserOrigin = typeof window !== 'undefined' ? window.location.origin : '';
const configuredApiRoot = (process.env.REACT_APP_API_URL || browserOrigin).replace(/\/api\/?$/, '').replace(/\/$/, '');
const configuredSimpleUrl = process.env.REACT_APP_API_SIMPLE_URL || configuredApiRoot;

export const API_URL = `${configuredApiRoot}/api`;
export const API_SIMPLE_URL = configuredSimpleUrl.replace(/\/$/, '');
export const SOCKET_URL = process.env.REACT_APP_SOCKET_URL || '';
