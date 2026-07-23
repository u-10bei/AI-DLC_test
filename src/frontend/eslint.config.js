import js from '@eslint/js'
import tseslint from '@typescript-eslint/eslint-plugin'
import tsparser from '@typescript-eslint/parser'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'

export default [
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsparser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
      globals: { window: 'readonly', document: 'readonly', fetch: 'readonly', FormData: 'readonly', File: 'readonly', console: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly' },
    },
    plugins: { '@typescript-eslint': tseslint, react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...reactHooks.configs.recommended.rules,

      // TypeScript already checks these; the core rules produce false positives on
      // types (BodyInit, JSX, RequestInit) and type-only parameter names.
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],

      // PAT-FE-12 (NFR-FE-SEC2): XSS-safe rendering. No raw HTML injection.
      'react/no-danger': 'error',

      // PAT-FE-14 / H-5: the frontend must not import any backend unit. src/frontend
      // is a sibling of the Python packages under the repo's src/; any relative import
      // that climbs out of this project reaches backend code. Forbid it here so the
      // lint gate fails — the TypeScript analog of the backend's import-linter R-8.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['../../../*', '../../../../*', '/**/src/shared_kernel/*', '/**/src/api_orchestration/*'],
              message:
                'H-5: the frontend must talk to the backend over REST only (NFR-M05); importing backend code is forbidden.',
            },
          ],
        },
      ],
    },
  },
]
