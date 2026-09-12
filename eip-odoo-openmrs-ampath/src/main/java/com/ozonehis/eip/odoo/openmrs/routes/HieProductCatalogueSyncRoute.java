/*
 * Copyright © 2021, Ozone HIS <info@ozone-his.com>
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */
package com.ozonehis.eip.odoo.openmrs.routes;

import com.ozonehis.eip.odoo.openmrs.handlers.hie.HieProductCatalogueSynchronizer;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;
import org.apache.camel.builder.RouteBuilder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Scheduled Camel route for HIE → OpenMRS + Odoo product catalogue sync.
 * Default period: once per day ({@code EIP_HIE_PRODUCT_SYNC_DELAY=86400000}).
 */
@Slf4j
@Setter
@Component
public class HieProductCatalogueSyncRoute extends RouteBuilder {

    public static final String ROUTE_ID = "hie-product-catalogue-sync";

    @Value("${eip.hie.product.sync.enabled:false}")
    private boolean enabled;

    @Value("${eip.hie.product.sync.delay:86400000}")
    private long delayMs;

    @Value("${eip.hie.product.sync.initial.delay:60000}")
    private long initialDelayMs;

    @Autowired
    private HieProductCatalogueSynchronizer synchronizer;

    @Override
    public void configure() {
        // spotless:off
        from("timer:hieProductCatalogueSync?delay=" + initialDelayMs + "&period=" + delayMs)
                .routeId(ROUTE_ID)
                .autoStartup(enabled)
                .log("HIE product catalogue sync timer fired (enabled=" + enabled + ")")
                .doTry()
                    .bean(synchronizer, "sync")
                    .log("HIE product catalogue sync finished successfully")
                .doCatch(Exception.class)
                    .log(org.apache.camel.LoggingLevel.ERROR,
                            "HIE product catalogue sync failed: ${exception.message}")
                .end();
        // spotless:on
    }
}
