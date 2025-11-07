
/** Get level's first (or sole) recorded front path. */
export function getFirstFrontPath(level) {  
  if (Array.isArray(level.frontPath)) {
    return level.frontPath[0];
  }
  return level.frontPath;
}

/** Get array of all front paths (possibly one or zero) for a level. */
export function getAllFrontPaths(level) {
  if (Array.isArray(level.frontPath)) {
    return level.frontPath;
  }
  if (typeof level.frontPath === 'string') {
    return [level.frontPath];
  }
  return [];
}
