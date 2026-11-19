package com.atbm.app.data.api

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ServerAddressTest {

    @Test
    fun bareIpGetsHttpsAndDevPort() {
        assertEquals("https://192.168.1.38:8443/", ServerAddress.normalize(" 192.168.1.38 "))
        assertEquals("https://192.168.1.38:8443/", ServerAddress.normalize("192.168.1.38/"))
    }

    @Test
    fun explicitPortIsKept() {
        assertEquals("https://192.168.1.38:9000/", ServerAddress.normalize("192.168.1.38:9000"))
        assertEquals("https://10.0.2.2:8443/", ServerAddress.normalize("https://10.0.2.2:8443/"))
    }

    @Test
    fun httpsDomainKeepsDefaultPort() {
        assertEquals("https://api.vd.vn/", ServerAddress.normalize("https://api.vd.vn"))
    }

    @Test
    fun rejectsCleartextAndGarbage() {
        assertNull(ServerAddress.normalize("http://192.168.1.38:8443"))
        assertNull(ServerAddress.normalize(""))
        assertNull(ServerAddress.normalize("192.168 .1.38"))
        assertNull(ServerAddress.normalize("ftp://x"))
    }

    @Test
    fun displayIsShortForm() {
        assertEquals("192.168.1.38", ServerAddress.display("https://192.168.1.38:8443/"))
        assertEquals("192.168.1.38:9000", ServerAddress.display("https://192.168.1.38:9000/"))
        assertEquals("https://api.vd.vn", ServerAddress.display("https://api.vd.vn/"))
    }
}
