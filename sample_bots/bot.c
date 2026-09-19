#include <stdlib.h>
#include <math.h>

// Note: The 'Swap' struct is pre-defined by the server environment as:
// typedef struct { int r1, c1, r2, c2; } Swap;

Swap* get_swaps(int** matrix, int R, int C, int* out_num_swaps) {
    // 1. Tell the server how many swaps we are returning
    *out_num_swaps = 1;
    
    // 2. Allocate the memory for the swaps
    Swap* swaps = (Swap*)malloc((*out_num_swaps) * sizeof(Swap));
    
    // 3. Populate the swaps (0-indexed)
    // example, swap (0, 0) for (0, 4)
    swaps[0].r1 = 0;
    swaps[0].c1 = 0;
    swaps[0].r2 = 0;
    swaps[0].c2 = 4;
    
    return swaps;
}