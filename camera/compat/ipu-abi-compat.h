/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Constants the ipu4 port expects from Intel's out-of-tree changes to core
 * v4l2/media uapi headers. Force-included (-include) when building against
 * stock distro headers; these are additive #defines only, nothing here
 * changes the layout of a struct the running kernel shares with us.
 *
 * The struct changes from the same patch (v4l2_subdev_pad_ops.get_routing,
 * v4l2_mbus_frame_desc_entry.bpp/two_dim) are handled in the driver source,
 * see patches/0001-ipu4-build-against-stock-v4l2-headers.patch.
 */
#ifndef IPU_ABI_COMPAT_H
#define IPU_ABI_COMPAT_H

#include <linux/videodev2.h>
#include <linux/v4l2-controls.h>
#include <linux/v4l2-subdev.h>
#include <linux/media.h>

/* media.h: driver-private pad flag, never reported through MEDIA_IOC_* */
#ifndef MEDIA_PAD_FL_MULTIPLEX
#define MEDIA_PAD_FL_MULTIPLEX			(1U << 3)
#endif

/* v4l2-subdev.h: route flags used only on the driver's own route tables */
#ifndef V4L2_SUBDEV_ROUTE_FL_IMMUTABLE
#define V4L2_SUBDEV_ROUTE_FL_IMMUTABLE		(1U << 1)
#endif
#ifndef V4L2_SUBDEV_ROUTE_FL_SOURCE
#define V4L2_SUBDEV_ROUTE_FL_SOURCE		(1U << 2)
#endif
#ifndef V4L2_SUBDEV_FLAG_NEXT_STREAM
#define V4L2_SUBDEV_FLAG_NEXT_STREAM		0x80000000
#endif

/* v4l2-controls.h */
#ifndef V4L2_CID_MIPI_LANES
#define V4L2_CID_MIPI_LANES		(V4L2_CID_IMAGE_SOURCE_CLASS_BASE + 64)
#endif

/* videodev2.h: IPU "vector" raw/YUV layouts */
#ifndef V4L2_PIX_FMT_SBGGR8_16V32
#define V4L2_PIX_FMT_SBGGR8_16V32	v4l2_fourcc('b', 'V', '0', 'A')
#define V4L2_PIX_FMT_SGBRG8_16V32	v4l2_fourcc('b', 'V', '0', 'B')
#define V4L2_PIX_FMT_SGRBG8_16V32	v4l2_fourcc('b', 'V', '0', 'C')
#define V4L2_PIX_FMT_SRGGB8_16V32	v4l2_fourcc('b', 'V', '0', 'D')
#endif
#ifndef V4L2_PIX_FMT_SBGGR8V32
#define V4L2_PIX_FMT_SBGGR8V32		v4l2_fourcc('b', 'V', '0', 'A')
#define V4L2_PIX_FMT_SGBRG8V32		v4l2_fourcc('b', 'V', '0', 'B')
#define V4L2_PIX_FMT_SGRBG8V32		v4l2_fourcc('b', 'V', '0', 'C')
#define V4L2_PIX_FMT_SRGGB8V32		v4l2_fourcc('b', 'V', '0', 'D')
#endif
#ifndef V4L2_PIX_FMT_SBGGR10V32
#define V4L2_PIX_FMT_SBGGR10V32		v4l2_fourcc('b', 'V', '0', 'E')
#define V4L2_PIX_FMT_SGBRG10V32		v4l2_fourcc('b', 'V', '0', 'F')
#define V4L2_PIX_FMT_SGRBG10V32		v4l2_fourcc('b', 'V', '0', 'G')
#define V4L2_PIX_FMT_SRGGB10V32		v4l2_fourcc('b', 'V', '0', 'H')
#endif
#ifndef V4L2_PIX_FMT_SBGGR12V32
#define V4L2_PIX_FMT_SBGGR12V32		v4l2_fourcc('b', 'V', '0', 'I')
#define V4L2_PIX_FMT_SGBRG12V32		v4l2_fourcc('b', 'V', '0', 'J')
#define V4L2_PIX_FMT_SGRBG12V32		v4l2_fourcc('b', 'V', '0', 'K')
#define V4L2_PIX_FMT_SRGGB12V32		v4l2_fourcc('b', 'V', '0', 'L')
#endif
#ifndef V4L2_PIX_FMT_SBGGR14V32
#define V4L2_PIX_FMT_SBGGR14V32		v4l2_fourcc('b', 'V', '0', 'M')
#define V4L2_PIX_FMT_SGBRG14V32		v4l2_fourcc('b', 'V', '0', 'N')
#define V4L2_PIX_FMT_SGRBG14V32		v4l2_fourcc('b', 'V', '0', 'O')
#define V4L2_PIX_FMT_SRGGB14V32		v4l2_fourcc('b', 'V', '0', 'P')
#endif
#ifndef V4L2_PIX_FMT_UYVY_V32
#define V4L2_PIX_FMT_UYVY_V32		v4l2_fourcc('y', 'V', '3', '2')
#endif
#ifndef V4L2_PIX_FMT_YUYV420_V32
#define V4L2_PIX_FMT_YUYV420_V32	v4l2_fourcc('y', '0', '3', '2')
#endif

#endif /* IPU_ABI_COMPAT_H */
