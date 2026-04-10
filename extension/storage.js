/** Storage area wrapper. */
class Storage {

  /** Builds wrapper, retrieves all stored data on worker (re)start. */
  constructor(storageArea) {
    this.storageArea = storageArea;
    storageArea.get(storedData => {
      Object.assign(this, storedData);
    });
  }

  /** Stores items, updates wrapper references. */
  store(items) {
    this.storageArea.set(items);
    Object.assign(this, items);
  }
}

/** Unified interface for the `chrome.storage` API. */
export const storage = {
  session: new Storage(chrome.storage.session),
};
