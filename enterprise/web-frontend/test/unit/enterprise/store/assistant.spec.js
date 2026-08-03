import { getters } from '@baserow_enterprise/store/assistant'

describe('assistant store', () => {
  describe('uiContext getter', () => {
    test('does not throw when no workspace is resolvable from the current scope', () => {
      const rootGetters = {
        'undoRedo/getCurrentScope': {},
        'workspace/get': () => undefined,
      }

      expect(() =>
        getters.uiContext(undefined, undefined, undefined, rootGetters)
      ).not.toThrow()

      const uiContext = getters.uiContext(
        undefined,
        undefined,
        undefined,
        rootGetters
      )
      expect(uiContext.workspace).toBe(null)
    })

    test('populates workspace when the scope resolves to a real workspace', () => {
      const workspace = { id: 5, name: 'Acme' }
      const rootGetters = {
        'undoRedo/getCurrentScope': { workspace: 5 },
        'workspace/get': (id) => (id === 5 ? workspace : undefined),
      }

      const uiContext = getters.uiContext(
        undefined,
        undefined,
        undefined,
        rootGetters
      )
      expect(uiContext.workspace).toEqual({ id: 5, name: 'Acme' })
    })
  })
})
