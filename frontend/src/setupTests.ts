import '@testing-library/jest-dom/vitest';
import { expect } from 'vitest';
import { toHaveNoViolations } from 'jest-axe';
import globalStyles from './styles/global.css?raw';
import themeStyles from './styles/theme.css?raw';
import appStyles from './styles.css?raw';

expect.extend(toHaveNoViolations);

const styleTag = document.createElement('style');
styleTag.innerHTML = `${globalStyles}\n${themeStyles}\n${appStyles}`;
document.head.appendChild(styleTag);
