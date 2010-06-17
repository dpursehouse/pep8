package com.sonyericsson.permissiongen;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;

/**
 * This class (together with the shell script) implements
 * a simple way to extract all information related to
 * permissions in the AndroidManifest.xml file to a
 * html file in order to present the information in one place
 *
 * @author kenneth.andersson@sonyericsson.com
 */
public class Generate {
    public static void main(String[] args) throws ParserConfigurationException, SAXException, IOException {
        try {
            String tagName = "";
            String resPath = "";
            String manifestFile = "";
            // Parse command line options
            for (int i = 0; i < args.length; i++) {
                String arg = args[i];
                if ("-t".equals(arg)) {
                    i++;
                    tagName = args[i];
                } else if ("-r".equals(arg)) {
                    i++;
                    resPath = args[i];
                } else if ("-m".equals(arg)) {
                    i++;
                    manifestFile = args[i];
                } else if ("-h".equals(arg) || "--help".equals(arg)) {
                    usage();
                } else {
                    System.err.println("Unknown command line option '" + arg + "'!");
                    System.exit(1);
                }
            }
            if (resPath.equals("") || manifestFile.equals("")) {
                System.err.println("Missing resource or manifest path");
                System.exit(1);
            }
            ArrayList<PermissionEntry> entries = parseManifest(new File(manifestFile));
            lookupLabelAndDescription(entries, new File(resPath));
            generateHtmlReport(tagName, entries);
        } catch (Throwable t) {
        }
    }

    /**
     * Print usage information
     */
    private static void usage() {
        System.out.println("Usage: Generate [options]");
        System.out.println("Options:");
        System.out.println("    -h              : show this help");
        System.out.println("    -t tag          : tag name");
        System.out.println("    -r file         : resource folder");
        System.out.println("    -m file         : manifest");
    }

    /**
     * Parse the manifest file and extract a list of all entries in all manifests
     */
    private static ArrayList<PermissionEntry> parseManifest(File fin) throws ParserConfigurationException, SAXException, IOException {
        ArrayList<PermissionEntry> result = new ArrayList<PermissionEntry>();
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        DocumentBuilder db = dbf.newDocumentBuilder();
        Document doc = db.parse(fin);
        doc.getDocumentElement().normalize();
        NodeList nodeLst = doc.getElementsByTagName("permission");
        for (int s = 0; s < nodeLst.getLength(); s++) {
            Node fstNode = nodeLst.item(s);
            if (fstNode.getNodeType() == Node.ELEMENT_NODE) {
                Element fstElmnt = (Element) fstNode;
                result.add(new PermissionEntry(fstElmnt.getAttribute("android:name"),
                        fstElmnt.getAttribute("android:permissionGroup"),
                        fstElmnt.getAttribute("android:protectionLevel"),
                        fstElmnt.getAttribute("android:label"),
                        fstElmnt.getAttribute("android:description")));
            }
        }
        return result;
    }

    /**
     * Use a generated list of entries and lookup the tags in the resources folder to produce the real description
     */
    private static void lookupLabelAndDescription(ArrayList<PermissionEntry> entries, File resFolder) throws SAXException, IOException, ParserConfigurationException {
        File[] files = resFolder.listFiles();
        for (int i = 0;files != null && i<files.length; i++) {
            if (files[i].isFile()) {
                DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
                DocumentBuilder db = dbf.newDocumentBuilder();
                Document doc = db.parse(files[i]);
                doc.getDocumentElement().normalize();
                NodeList nodeLst = doc.getElementsByTagName("string");
                for (int j = 0; j<nodeLst.getLength(); j++) {
                    Node fstNode = nodeLst.item(j);
                    if (fstNode.getNodeType() == Node.ELEMENT_NODE) {
                        Element fstElmnt = (Element) fstNode;
                        for (int k = 0; k<entries.size(); k++) {
                            PermissionEntry current = entries.get(k);
                            if (fstElmnt.getAttribute("name").equals(current.getDescriptionTag())) {
                                NodeList fstNm = fstElmnt.getChildNodes();
                                current.setDescription(fstNm.item(0).getNodeValue().replace("\n", "").replace("\t"," "));
                            }
                            if (fstElmnt.getAttribute("name").equals(current.getLabelTag())) {
                                NodeList fstNm = fstElmnt.getChildNodes();
                                current.setLabel(fstNm.item(0).getNodeValue().replace("\n", "").replace("\t"," "));
                            }
                        }
                    }
                }
            }
        }
    }

    /**
     * Generate simple html report of all entries.
     */
    private static void generateHtmlReport(String tag, ArrayList<PermissionEntry> entries) {
        if (entries.size() == 0) {
            return;
        }
        System.out.println("<tr>");
        System.out.println("<td colspan=\"5\" style=\"font-family:verdana;font-size:80%\" align=\"left\">" + tag + "</td>");
        System.out.println("</tr>");
        for (int i = 0;i<entries.size();i++) {
            System.out.println("<tr>");
            System.out.println("<td style=\"font-family:verdana;font-size:80%\" align=\"left\">" + entries.get(i).getPermissionName() + "</td>");
            System.out.println("<td style=\"font-family:verdana;font-size:80%\" align=\"left\">" + entries.get(i).getDescription() + "</td>");
            System.out.println("<td style=\"font-family:verdana;font-size:80%\" align=\"left\">" + entries.get(i).getLabel() + "</td>");
            System.out.println("<td style=\"font-family:verdana;font-size:80%\" align=\"left\">" + entries.get(i).getPermissionGroup() + "</td>");
            System.out.println("<td style=\"font-family:verdana;font-size:80%\" align=\"left\">" + entries.get(i).getProtectionLevel() + "</td>");
            System.out.println("</tr>");
        }
    }
}

