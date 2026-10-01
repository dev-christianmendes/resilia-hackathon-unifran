/** @type {import('@commitlint/types').UserConfig} */
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'perf',
        'refactor',
        'style',
        'docs',
        'test',
        'build',
        'ci',
        'chore',
        'revert',
      ],
    ],
    'subject-case': [0],
    // 'scope-empty' desativado: neste projeto o escopo e obrigatorio, e a
    // config padrao o trata como proibido. A lista abaixo e o que aceitamos.
    'scope-empty': [0],
    'scope-enum': [
      2,
      'always',
      ['repo', 'setup', 'schemas', 'data', 'ingest', 'engine', 'ai', 'api', 'backend', 'frontend'],
    ],
    'body-max-line-length': [0],
  },
};
