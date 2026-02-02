<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
    <%@page import="model.AddrDTO"%>
    <%@page import="model.AddrDAO"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>주소록 등록</title>
<link rel="stylesheet" type= "text/css" href="../css/join.css" />
</head>
<body>
<% request.setCharacterEncoding("utf-8"); %>

<!-- 객체 addr 프론트에서 DTO로 보내기-->
<jsp:useBean class ="model.AddrDTO" id="addr">
<jsp:setProperty name="addr" property="*"/>
</jsp:useBean>

<!-- 객체 am  백엔드에서 프론트로 불러오기-->
<jsp:useBean class ="model.AddrDAO" id="am" scope="application"/>
<% am.add(addr); %>
<div class ="container">
<h2>등록 완료</h2>
<p>이름 : <jsp:getProperty name="addr" property="username"/></p>
<p>전화번호 : <jsp:getProperty name="addr" property="tel"/></p>
<p>이메일 : <jsp:getProperty name="addr" property="email"/></p>
<p>성별 : <jsp:getProperty name="addr" property="gender"/></p>
<hr />
<a href="addr_list.jsp">주소 목록 보기</a>

</div>
</body>
</html>