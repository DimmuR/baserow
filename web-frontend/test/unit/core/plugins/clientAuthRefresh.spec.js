import { makeRefreshAuthInterceptor } from '@baserow/modules/core/plugins/clientAuthRefresh'

describe('makeRefreshAuthInterceptor', () => {
  test('does not leave an unhandled rejection when the refresh call itself fails', async () => {
    const requestInterceptors = []
    const client = {
      interceptors: {
        request: { use: (fn) => requestInterceptors.push(fn) },
      },
    }

    const refreshError = Object.assign(
      new Error('Request failed with status code 429'),
      { isAxiosError: true, response: { status: 429 } }
    )
    const refreshAuthFunction = () => Promise.reject(refreshError)

    makeRefreshAuthInterceptor(
      client,
      refreshAuthFunction,
      () => true, // shouldInterceptRequest
      () => false // shouldInterceptResponse
    )

    const unhandled = []
    const onUnhandledRejection = (reason) => unhandled.push(reason)
    process.on('unhandledRejection', onUnhandledRejection)

    // The caller (the real axios request pipeline) always observes and
    // handles the promise returned by the interceptor itself, so any
    // unhandled rejection must come from an internally orphaned promise.
    await requestInterceptors[0]({}).catch(() => {})

    // Let Node's unhandled-rejection check run against the settled promises.
    await new Promise((resolve) => setImmediate(resolve))
    await new Promise((resolve) => setImmediate(resolve))

    process.off('unhandledRejection', onUnhandledRejection)

    expect(unhandled).toHaveLength(0)
  })
})
