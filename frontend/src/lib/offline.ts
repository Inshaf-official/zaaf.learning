import { useSession } from "../store";
import { api, ApiError } from "../api";
export interface PendingSave {
  id: string;
  membership: number;
  path: string;
  body: unknown;
  created: string;
  error?: string;
}
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("institution-outbox", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("pending", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function pending(membership: number): Promise<PendingSave[]> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction("pending", "readonly");
    const request = transaction.objectStore("pending").getAll();
    request.onsuccess = () =>
      resolve(
        (request.result as PendingSave[]).filter(
          (r) => r.membership === membership,
        ),
      );
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => db.close();
  });
}
export async function storePending(value: PendingSave): Promise<void> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("pending", "readwrite");
    tx.objectStore("pending").put(value);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}
export async function discard(id: string): Promise<void> {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("pending", "readwrite");
    tx.objectStore("pending").delete(id);
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => reject(tx.error);
  });
}
export async function replay(membership: number): Promise<void> {
  for (const item of await pending(membership)) {
    if (useSession.getState().membership?.id !== membership) return;
    try {
      await api(item.path, { method: "POST", body: item.body });
      await discard(item.id);
    } catch (error) {
      if (error instanceof ApiError)
        await storePending({ ...item, error: error.message });
      break;
    }
  }
}
