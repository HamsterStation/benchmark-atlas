import { micromark } from 'micromark';
// Raw HTML and dangerous protocols stay disabled; Markdown is never build code.
export const renderNote = text => micromark(text, { allowDangerousHtml: false, allowDangerousProtocol: false });
