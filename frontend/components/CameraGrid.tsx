'use client';

import { useState } from 'react';
import { WebRTCVideo } from './WebRTCVideo';

export type Camera = { id: string; name: string; status: 'online' | 'offline' };

export function CameraGrid({ cameras = [] }: { cameras?: Camera[] }) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleError = (cameraId: string, error: string) => {
    setErrors(prev => ({ ...prev, [cameraId]: error }));
  };

  const handleConnected = (cameraId: string) => {
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[cameraId];
      return newErrors;
    });
  };

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {cameras.map((camera) => (
        <article key={camera.id} className="rounded-lg border p-4 shadow-sm flex flex-col gap-3">
          <div>
            <h3 className="font-semibold">{camera.name}</h3>
            <p className="text-sm text-slate-500">Camera ID: {camera.id}</p>
          </div>

          {/* WebRTC Video Stream */}
          <div className="rounded-md overflow-hidden bg-black">
            <WebRTCVideo
              cameraId={camera.id}
              onError={(error) => handleError(camera.id, error)}
              onConnected={() => handleConnected(camera.id)}
            />
          </div>

          {/* Status and Error Messages */}
          {errors[camera.id] ? (
            <div className="text-xs bg-red-50 text-red-700 p-2 rounded">
              ⚠️ {errors[camera.id]}
            </div>
          ) : (
            <p className="text-xs text-green-600">✅ Connected</p>
          )}
        </article>
      ))}
    </section>
  );
}
