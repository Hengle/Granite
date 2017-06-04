#version 310 es

#include "inc/render_parameters.h"

layout(location = 0) in highp vec3 Position;

#if HAVE_VERTEX_COLOR
layout(location = 1) in mediump vec4 Color;
layout(location = 0) out mediump vec4 vCOlor;
#endif

layout(std430, push_constant) uniform Model
{
    mat4 MVP;
} registers;

void main()
{
    gl_Position = registers.MVP * vec4(Position, 1.0);
#if HAVE_VERTEX_COLOR
    vColor = Color;
#endif
}

