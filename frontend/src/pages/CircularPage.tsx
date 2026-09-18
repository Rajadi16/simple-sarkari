/**
 * Circular detail page — shows original, simplified, translated text + audio.
 */

import { useParams } from "react-router-dom";

export default function CircularPage() {
  const { id } = useParams<{ id: string }>();

  // TODO: Fetch circular, translations, audio using TanStack Query
  return (
    <div>
      <h1>Circular Detail</h1>
      <p>Circular ID: {id}</p>
      {/* TODO: Original text, simplified text, translation tabs, AudioPlayer */}
    </div>
  );
}
